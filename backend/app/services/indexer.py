"""
Indexer service - Orchestrates chunking, embedding, and storage.
"""

import chromadb
from pathlib import Path
from typing import List, Optional

from app.config import settings
from app.utils.logger import get_logger
from app.models.repo import RepoInfo
from app.models.chunk import Chunk
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
    
    BATCH_SIZE = 100  # Number of chunks to embed/insert at once
    
    def _get_db_path(self, repo_info: RepoInfo) -> Path:
        """Get path for vector store."""
        return Path(repo_info.local_path) / "index"
    
    def _get_client(self, db_path: Path) -> chromadb.ClientAPI:
        """Get ChromaDB client for specific path."""
        db_path.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(db_path))
    
    async def index_repo(self, repo_id: str) -> dict:
        """
        Full indexing workflow for a repository.
        """
        logger.info("indexing_started", repo_id=repo_id)
        
        # 1. Get repo info
        repo_info = repo_manager.get_repo(repo_id)
        if not repo_info:
            raise RepoManagerError(f"Repository not found: {repo_id}")
        
        # 2. List and read files
        files = await repo_manager.list_files(repo_id)
        file_contents = {}
        
        for file_meta in files:
            path = file_meta["file_path"]
            try:
                content = await repo_manager.get_file_content(repo_id, path)
                file_contents[path] = content
            except Exception:
                continue
        
        logger.info("files_read", count=len(file_contents))
        
        # 3. Chunk files
        chunks, stats = await chunker.chunk_repository(repo_id, file_contents)
        
        if not chunks:
            logger.warning("no_chunks_created", repo_id=repo_id)
            return {"indexed": True, "chunk_count": 0}
        
        # 4. Prepare ChromaDB
        db_path = self._get_db_path(repo_info)
        client = self._get_client(db_path)
        
        # Delete existing collection if any
        try:
            client.delete_collection("repo_index")
        except Exception:
            # Collection doesn't exist or other error - safe to ignore
            pass
        
        collection = client.create_collection(
            name="repo_index",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 5. Embed and Insert in batches
        total_chunks = len(chunks)
        
        for i in range(0, total_chunks, self.BATCH_SIZE):
            batch = chunks[i : i + self.BATCH_SIZE]
            
            # Prepare data
            documents = [c.content for c in batch]
            ids = [c.metadata.chunk_id for c in batch]
            metadatas = [c.metadata.model_dump() for c in batch]
            
            # Generate embeddings
            embeddings = await embedding_service.embed_batch(documents)
            
            # Insert
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.debug(
                "batch_indexed", 
                batch=i//self.BATCH_SIZE + 1, 
                count=len(batch)
            )
        
        # 6. Update repo state
        repo_info.indexed = True
        repo_info.chunk_count = total_chunks
        
        logger.info(
            "indexing_complete", 
            repo_id=repo_id, 
            chunks=total_chunks
        )
        
        return {
            "indexed": True,
            "chunk_count": total_chunks,
            "stats": stats.model_dump()
        }
    
    def get_collection(self, repo_id: str) -> Optional[chromadb.Collection]:
        """Get the collection for query purposes."""
        repo_info = repo_manager.get_repo(repo_id)
        if not repo_info:
            logger.warning("repo_not_found_for_collection", repo_id=repo_id)
            return None
        
        # Try to open the collection directly without checking indexed flag
        # (The collection on disk is the source of truth)
        db_path = self._get_db_path(repo_info)
        
        if not db_path.exists():
            logger.warning("db_path_not_found", repo_id=repo_id, path=str(db_path))
            return None
            
        try:
            client = self._get_client(db_path)
            collection = client.get_collection("repo_index")
            logger.info("collection_opened", repo_id=repo_id, count=collection.count())
            return collection
        except Exception as e:
            # Collection doesn't exist or other error
            logger.warning("collection_not_found", repo_id=repo_id, error=str(e))
            return None


# Global instance
indexer = Indexer()
