"""
Indexer service - Orchestrates chunking, embedding, and storage.

Supports two modes:
- **Ephemeral** (USE_PERSISTENT_INDEX=false): in-memory ChromaDB, rebuilt every time.
- **Persistent** (USE_PERSISTENT_INDEX=true): on-disk ChromaDB with commit-hash
  staleness detection.  Skips re-indexing when the stored commit matches the
  current repo state.
"""

import asyncio
import chromadb
import json as _json
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings
from app.utils.logger import get_logger
from app.models.repo import RepoInfo
from app.services.repo_manager import repo_manager, RepoManagerError
from app.services.chunker import chunker
from app.utils.embeddings import embedding_service

logger = get_logger(__name__)


class Indexer:
    """
    Manages the indexing process:
    1. Scan files
    2. Chunk files
    3. Generate embeddings
    4. Store in ChromaDB
    """

    def __init__(self):
        # Number of chunks to embed/insert at once
        self.batch_size = max(25, settings.index_batch_size)
        # Concurrent file reads before chunking
        self.file_read_concurrency = max(1, settings.file_read_concurrency)
        # Fast indexing guardrails (favor < 1 minute indexing over full coverage)
        self.max_index_files = max(200, settings.index_max_files)
        self.max_file_size_bytes = max(32 * 1024, settings.index_max_file_size_kb * 1024)
        self.max_index_total_bytes = max(8, settings.index_max_total_mb) * 1024 * 1024
        self.max_chunks = max(500, settings.index_max_chunks)
        self.time_budget_seconds = max(20, settings.index_time_budget_seconds)
        self.use_persistent_index = settings.use_persistent_index
        self._ephemeral_client: Optional[chromadb.ClientAPI] = None
        # Cache persistent clients by db_path to avoid re-creating on every query
        self._persistent_clients: Dict[str, chromadb.ClientAPI] = {}
        if not self.use_persistent_index:
            self._ephemeral_client = chromadb.EphemeralClient()

    def _get_db_path(self, repo_info: RepoInfo) -> Path:
        """Get path for vector store."""
        return settings.data_dir / "_indexes" / repo_info.repo_id

    def _collection_name(self, repo_id: str) -> str:
        """Stable collection name per repository."""
        return f"repo_{repo_id}"

    def _get_client(self, db_path: Path) -> chromadb.ClientAPI:
        """Get or create a ChromaDB PersistentClient for the given path.

        Clients are cached so repeated ``get_collection`` calls don't
        re-open the database every time.
        """
        key = str(db_path)
        if key in self._persistent_clients:
            return self._persistent_clients[key]
        db_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=key)
        self._persistent_clients[key] = client
        return client

    # ── Staleness detection ───────────────────────────────────────

    _INDEX_META_FILE = "_index_meta.json"

    def _meta_path(self, db_path: Path) -> Path:
        """Path to the JSON metadata file stored alongside the ChromaDB data."""
        return db_path / self._INDEX_META_FILE

    def _read_index_meta(self, db_path: Path) -> Optional[dict]:
        """Read the cached index metadata (commit_hash, chunk_count, etc.)."""
        meta_file = self._meta_path(db_path)
        if not meta_file.exists():
            return None
        try:
            return _json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_index_meta(
        self, db_path: Path, commit_hash: str, chunk_count: int
    ) -> None:
        """Persist index metadata next to the ChromaDB data."""
        meta_file = self._meta_path(db_path)
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        meta_file.write_text(
            _json.dumps(
                {
                    "commit_hash": commit_hash,
                    "chunk_count": chunk_count,
                    "indexed_at": time.time(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _is_index_fresh(self, repo_info: RepoInfo, force: bool = False) -> bool:
        """Return True if the persistent index is up-to-date for this repo.

        An index is fresh when:
        - ``force`` is False
        - The metadata file exists
        - The stored commit_hash matches ``repo_info.commit_hash``
        - The ChromaDB directory actually contains data
        """
        if force:
            return False
        db_path = self._get_db_path(repo_info)
        meta = self._read_index_meta(db_path)
        if meta is None:
            return False
        if meta.get("commit_hash") != repo_info.commit_hash:
            logger.info(
                "index_stale_commit_changed",
                repo_id=repo_info.repo_id,
                stored=meta.get("commit_hash"),
                current=repo_info.commit_hash,
            )
            return False
        # Verify the ChromaDB directory actually has content
        if not (db_path / "chroma.sqlite3").exists():
            return False
        return True

    def _priority_for_file(self, file_meta: dict) -> tuple[int, int, int]:
        """
        Lower tuple means higher priority.
        Prioritize likely code files close to repo root and mid-size files.
        """
        language = (file_meta.get("language") or "").lower()
        file_path = file_meta.get("file_path", "")
        size = int(file_meta.get("size", 0))
        depth = file_path.count("/")

        code_languages = {
            "py", "js", "ts", "jsx", "tsx", "java", "go", "rs", "rb", "c",
            "cpp", "h", "hpp", "cs", "swift", "kt", "scala", "php", "lua",
            "sh", "bash", "ps1", "psm1", "cmd", "bat",
        }
        config_languages = {
            "json", "yaml", "yml", "toml", "ini", "cfg", "conf", "xml",
            "dockerfile", "makefile", "gitignore", "gitattributes",
        }

        if language in code_languages:
            type_rank = 0
        elif language in config_languages:
            type_rank = 1
        else:
            type_rank = 2

        # Prefer files that are substantial but not massive.
        target_size = 24 * 1024
        size_rank = abs(size - target_size)
        return (type_rank, depth, size_rank)

    def _select_files_for_index(self, files: List[dict]) -> List[dict]:
        """
        Pick a bounded subset of files for fast indexing.
        """
        eligible = [
            f for f in files
            if int(f.get("size", 0)) > 0 and int(f.get("size", 0)) <= self.max_file_size_bytes
        ]

        eligible.sort(key=self._priority_for_file)

        selected: List[dict] = []
        selected_bytes = 0

        for file_meta in eligible:
            if len(selected) >= self.max_index_files:
                break

            size = int(file_meta.get("size", 0))
            if selected_bytes + size > self.max_index_total_bytes:
                continue

            selected.append(file_meta)
            selected_bytes += size

        if not selected and eligible:
            # Always include at least one file if any file is eligible.
            selected = [eligible[0]]

        logger.info(
            "index_selection_complete",
            total_files=len(files),
            eligible_files=len(eligible),
            selected_files=len(selected),
            selected_mb=round(selected_bytes / (1024 * 1024), 2),
        )
        return selected

    async def index_repo(self, repo_id: str, force: bool = False) -> dict:
        """
        Full indexing workflow for a repository.

        When ``use_persistent_index`` is enabled the method first checks
        whether the on-disk index is still fresh (same commit hash).  If
        fresh, it returns immediately without any embedding work.
        """
        logger.info("indexing_started", repo_id=repo_id)

        # 1. Get repo info
        repo_info = repo_manager.get_repo(repo_id)
        if not repo_info:
            raise RepoManagerError(f"Repository not found: {repo_id}")

        # ── Persistent-index shortcut: skip if already up-to-date ──
        if self.use_persistent_index and self._is_index_fresh(repo_info, force=force):
            meta = self._read_index_meta(self._get_db_path(repo_info))
            cached_chunks = (meta or {}).get("chunk_count", 0)
            logger.info(
                "index_cache_hit",
                repo_id=repo_id,
                commit=repo_info.commit_hash[:8],
                chunks=cached_chunks,
            )
            repo_manager.update_repo(
                repo_id,
                persist=True,
                is_indexing=False,
                indexed=True,
                index_progress_pct=100.0,
                chunk_count=cached_chunks,
                index_processed_chunks=cached_chunks,
                index_total_chunks=cached_chunks,
            )
            return {"indexed": True, "chunk_count": cached_chunks, "from_cache": True}

        repo_manager.update_repo(
            repo_id,
            persist=True,
            is_indexing=True,
            indexed=False,
            index_progress_pct=1.0,
            index_processed_chunks=0,
            index_total_chunks=0,
            chunk_count=0,
        )

        try:
            # 2. List and read files
            files = await repo_manager.list_files(repo_id)
            selected_files = self._select_files_for_index(files)
            file_contents = {}
            indexing_start = time.monotonic()
            timed_out_during_index = False

            if not selected_files:
                logger.warning("no_files_selected_for_index", repo_id=repo_id)
                repo_manager.update_repo(
                    repo_id,
                    persist=True,
                    is_indexing=False,
                    indexed=True,
                    index_progress_pct=100.0,
                    chunk_count=0,
                    index_processed_chunks=0,
                    index_total_chunks=0,
                )
                return {"indexed": True, "chunk_count": 0}

            async def _read_file(file_meta: dict) -> tuple[str, Optional[str]]:
                path = file_meta["file_path"]
                try:
                    content = await repo_manager.get_file_content(repo_id, path)
                    return path, content
                except Exception:
                    return path, None

            total_files = len(selected_files)
            read_budget_seconds = self.time_budget_seconds * 0.45
            processed_file_count = 0

            for start in range(0, total_files, self.file_read_concurrency):
                elapsed = time.monotonic() - indexing_start
                if elapsed >= read_budget_seconds and file_contents:
                    timed_out_during_index = True
                    logger.warning(
                        "read_phase_budget_reached",
                        repo_id=repo_id,
                        elapsed_seconds=round(elapsed, 2),
                        processed_files=processed_file_count,
                        total_files=total_files,
                    )
                    break

                file_batch = selected_files[start : start + self.file_read_concurrency]
                batch_results = await asyncio.gather(*[_read_file(file_meta) for file_meta in file_batch])

                for path, content in batch_results:
                    if content is not None:
                        file_contents[path] = content

                processed_file_count += len(file_batch)
                if total_files > 0:
                    phase_pct = 2.0 + (processed_file_count / total_files) * 8.0
                    repo_manager.update_repo(
                        repo_id,
                        persist=False,
                        index_progress_pct=min(10.0, phase_pct),
                    )

            logger.info("files_read", count=len(file_contents))
            repo_manager.update_repo(repo_id, persist=False, index_progress_pct=10.0)

            # 3. Chunk files
            chunks, stats = await chunker.chunk_repository(repo_id, file_contents)
            if len(chunks) > self.max_chunks:
                logger.info(
                    "chunk_cap_applied",
                    repo_id=repo_id,
                    original_chunks=len(chunks),
                    capped_chunks=self.max_chunks,
                )
                chunks = chunks[: self.max_chunks]

            if not chunks:
                logger.warning("no_chunks_created", repo_id=repo_id)
                repo_manager.update_repo(
                    repo_id,
                    persist=True,
                    is_indexing=False,
                    indexed=True,
                    index_progress_pct=100.0,
                    chunk_count=0,
                    index_processed_chunks=0,
                    index_total_chunks=0,
                )
                return {"indexed": True, "chunk_count": 0}

            # 4. Prepare ChromaDB
            collection_name = self._collection_name(repo_id)
            if self.use_persistent_index:
                db_path = self._get_db_path(repo_info)
                # Evict the cached client for this path so we start clean
                self._persistent_clients.pop(str(db_path), None)
                if db_path.exists():
                    # Only delete when we are actually about to re-index
                    # (staleness check above already returned early if fresh)
                    await asyncio.to_thread(shutil.rmtree, db_path, ignore_errors=True)
                client = self._get_client(db_path)
            else:
                client = self._ephemeral_client or chromadb.EphemeralClient()
                self._ephemeral_client = client

            try:
                client.delete_collection(collection_name)
            except Exception:
                pass

            collection = client.create_collection(
                name=collection_name, metadata={"hnsw:space": "cosine"}
            )

            # 5. Embed and Insert in batches
            total_chunks = len(chunks)
            processed_chunks = 0

            repo_manager.update_repo(
                repo_id,
                persist=False,
                index_total_chunks=total_chunks,
                index_processed_chunks=0,
                index_progress_pct=15.0,
            )

            for i in range(0, total_chunks, self.batch_size):
                elapsed = time.monotonic() - indexing_start
                if elapsed >= self.time_budget_seconds and processed_chunks > 0:
                    timed_out_during_index = True
                    logger.warning(
                        "index_time_budget_reached",
                        repo_id=repo_id,
                        elapsed_seconds=round(elapsed, 2),
                        processed_chunks=processed_chunks,
                        total_chunks=total_chunks,
                    )
                    break

                batch = chunks[i : i + self.batch_size]

                # Prepare data
                documents = [c.content for c in batch]
                ids = [c.metadata.chunk_id for c in batch]
                metadatas = [c.metadata.model_dump() for c in batch]

                # Generate embeddings
                embeddings = await embedding_service.embed_batch(documents)

                # Insert
                await asyncio.to_thread(
                    collection.add,
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )

                processed_chunks += len(batch)
                progress_pct = 15.0 + (processed_chunks / total_chunks) * 84.0
                progress_pct = min(99.0, progress_pct)
                repo_manager.update_repo(
                    repo_id,
                    persist=False,
                    index_processed_chunks=processed_chunks,
                    index_progress_pct=progress_pct,
                )

                logger.debug(
                    "batch_indexed", batch=i // self.batch_size + 1, count=len(batch)
                )

            # 6. Update repo state and persist to registry
            final_chunk_count = processed_chunks
            repo_info.indexed = True
            repo_info.chunk_count = final_chunk_count
            repo_manager.update_repo(
                repo_id,
                persist=True,
                indexed=True,
                chunk_count=final_chunk_count,
                is_indexing=False,
                index_progress_pct=100.0,
                index_processed_chunks=final_chunk_count,
                index_total_chunks=total_chunks,
            )

            logger.info(
                "indexing_complete",
                repo_id=repo_id,
                chunks=final_chunk_count,
                partial=timed_out_during_index or final_chunk_count < total_chunks,
            )

            # Persist index metadata for future staleness checks
            if self.use_persistent_index:
                db_path = self._get_db_path(repo_info)
                self._write_index_meta(db_path, repo_info.commit_hash, final_chunk_count)

            return {
                "indexed": True,
                "chunk_count": final_chunk_count,
                "stats": stats.model_dump(),
            }
        except Exception:
            repo_manager.update_repo(repo_id, persist=True, is_indexing=False)
            raise

    def get_collection(self, repo_id: str) -> Optional[chromadb.Collection]:
        """Get the collection for query purposes."""
        repo_info = repo_manager.get_repo(repo_id)
        if not repo_info:
            logger.warning("repo_not_found_for_collection", repo_id=repo_id)
            return None

        collection_name = self._collection_name(repo_id)

        try:
            if self.use_persistent_index:
                db_path = self._get_db_path(repo_info)
                if not db_path.exists():
                    logger.warning("db_path_not_found", repo_id=repo_id, path=str(db_path))
                    return None
                client = self._get_client(db_path)
            else:
                client = self._ephemeral_client or chromadb.EphemeralClient()
                self._ephemeral_client = client

            collection = client.get_collection(collection_name)
            logger.info("collection_opened", repo_id=repo_id, count=collection.count())
            return collection
        except Exception as e:
            # Collection doesn't exist or other error
            logger.warning("collection_not_found", repo_id=repo_id, error=str(e))
            return None


# Global instance
indexer = Indexer()
