"""
RepoManager - Handles repository cloning, scanning, and filtering.
"""

import asyncio
import os
import re
import shutil
import subprocess
import json
import fnmatch
from pathlib import Path
from typing import Optional
from datetime import datetime
import hashlib
from uuid import uuid4
import tempfile

from app.config import settings
from app.utils.logger import get_logger
from app.models.repo import RepoInfo, RepoStats
import stat
import time

logger = get_logger(__name__)


def on_rm_error(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.
    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.
    If the error is for another reason it re-raises the error.
    """
    # Is the error an access error?
    os.chmod(path, stat.S_IWRITE)
    try:
        func(path)
    except Exception:
        # Retry once after small delay
        time.sleep(0.1)
        try:
            func(path)
        except Exception as e:
            logger.warning(f"Failed to delete {path}: {e}")


class RepoManagerError(Exception):
    """Base exception for RepoManager errors."""

    pass


class RepoTooLargeError(RepoManagerError):
    """Raised when repository exceeds size limits."""

    pass


class RepoCloneError(RepoManagerError):
    """Raised when repository cloning fails."""

    pass


class RepoManager:
    """
    Manages repository operations: clone, scan, filter.

    Workflow:
    1. load_repo(url) -> Clone repo to local storage
    2. scan_files(repo_id) -> List all eligible files
    3. get_file_content(repo_id, file_path) -> Read file contents
    """

    # File extensions to include
    INCLUDED_EXTENSIONS = {
        # Source code
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
        ".php",
        ".pl",
        ".r",
        ".m",
        ".mm",
        ".lua",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".psm1",
        ".bat",
        ".cmd",
        # Web
        ".html",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".vue",
        ".svelte",
        # Config
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".xml",
        ".env.example",
        ".env.sample",
        # Docs
        ".md",
        ".rst",
        ".txt",
        ".adoc",
        # Data
        ".sql",
        ".graphql",
        ".gql",
        # Other
        ".dockerfile",
        ".gitignore",
        ".gitattributes",
    }

    # Directories to exclude
    EXCLUDED_DIRS = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        "out",
        "target",
        ".next",
        ".nuxt",
        "coverage",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "vendor",
        "bower_components",
        "jspm_packages",
        ".idea",
        ".vscode",
        ".vs",
        "*.egg-info",
    }

    # Files to exclude
    EXCLUDED_FILES = {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.lock",
        "Gemfile.lock",
        "poetry.lock",
        ".DS_Store",
        "Thumbs.db",
    }

    # Filename for persisting repo registry
    REGISTRY_FILE = "repo_registry.json"

    def __init__(self):
        self._repos: dict[str, RepoInfo] = {}
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._load_registry()  # Load persisted repos on startup

    def _get_registry_path(self) -> Path:
        """Get path to the registry JSON file."""
        return settings.data_dir / self.REGISTRY_FILE

    def _load_registry(self):
        """Load repo registry from disk on startup."""
        path = self._get_registry_path()
        if not path.exists():
            logger.info("no_registry_found", path=str(path))
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for repo_id, info in data.items():
                # Validate that the local path still exists
                local_path = info.get("local_path")
                if local_path and Path(local_path).exists():
                    # Convert stats dict back to RepoStats if present
                    if "stats" in info and isinstance(info["stats"], dict):
                        info["stats"] = RepoStats(**info["stats"])
                    repo_info = RepoInfo(**info)
                    if not settings.use_persistent_index and repo_info.indexed:
                        # Ephemeral index storage is not persisted across restarts.
                        repo_info.indexed = False
                        repo_info.chunk_count = 0
                        repo_info.is_indexing = False
                        repo_info.index_progress_pct = 0.0
                        repo_info.index_processed_chunks = 0
                        repo_info.index_total_chunks = 0
                    self._repos[repo_id] = repo_info
                    logger.debug("recovered_repo", repo_id=repo_id)
                else:
                    logger.warning(
                        "repo_path_missing", repo_id=repo_id, path=local_path
                    )

            logger.info("registry_loaded", count=len(self._repos))
        except Exception as e:
            logger.warning("registry_load_failed", error=str(e))

    def _save_registry(self):
        """Persist repo registry to disk."""
        path = self._get_registry_path()
        try:
            data = {}
            for repo_id, info in self._repos.items():
                # Convert to dict, handling nested models
                info_dict = info.model_dump()
                data[repo_id] = info_dict

            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            logger.debug("registry_saved", count=len(data))
        except Exception as e:
            logger.error("registry_save_failed", error=str(e))

    def _parse_github_url(self, url: str) -> tuple[str, str]:
        """Extract owner and repo name from GitHub URL."""
        # HTTPS format: https://github.com/owner/repo.git
        https_match = re.match(
            r"https://github\.com/([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?$", url
        )
        if https_match:
            return https_match.group(1), https_match.group(2)

        # SSH format: git@github.com:owner/repo.git
        ssh_match = re.match(
            r"git@github\.com:([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?$", url
        )
        if ssh_match:
            return ssh_match.group(1), ssh_match.group(2)

        raise ValueError(f"Could not parse GitHub URL: {url}")

    def _generate_repo_id(self, repo_name: str, commit_hash: str) -> str:
        """Generate unique repo ID from name and commit."""
        combined = f"{repo_name}:{commit_hash[:8]}"
        return hashlib.sha256(combined.encode()).hexdigest()[:12]

    def _is_excluded_dir_name(self, dir_name: str) -> bool:
        """Check if a directory should be excluded from scans."""
        lowered = dir_name.lower()
        for pattern in self.EXCLUDED_DIRS:
            if "*" in pattern:
                if fnmatch.fnmatch(lowered, pattern.lower()):
                    return True
            elif lowered == pattern.lower():
                return True
        return False

    def _classify_file_name(self, file_name: str) -> Optional[str]:
        """
        Return normalized extension/language key for included files.
        Returns None when file should be excluded.
        """
        lowered = file_name.lower()

        if lowered in self.EXCLUDED_FILES:
            return None

        special_files = {
            "dockerfile": ".dockerfile",
            "makefile": ".makefile",
            "rakefile": ".rakefile",
            "gemfile": ".gemfile",
            ".gitignore": ".gitignore",
            ".gitattributes": ".gitattributes",
            ".env.example": ".env.example",
            ".env.sample": ".env.sample",
        }
        if lowered in special_files:
            return special_files[lowered]

        ext = Path(lowered).suffix
        if ext in self.INCLUDED_EXTENSIONS:
            return ext

        return None

    def _iter_candidate_files(self, repo_path: Path):
        """
        Yield candidate source/config/doc files quickly via os.walk pruning.
        """
        for root, dirs, files in os.walk(repo_path, topdown=True):
            dirs[:] = [d for d in dirs if not self._is_excluded_dir_name(d)]
            root_path = Path(root)

            for file_name in files:
                normalized_ext = self._classify_file_name(file_name)
                if not normalized_ext:
                    continue

                full_path = root_path / file_name
                try:
                    relative_path = full_path.relative_to(repo_path).as_posix()
                except Exception:
                    continue

                yield full_path, relative_path, normalized_ext

    async def _safe_remove_tree(self, path: Path, attempts: int = 3, delay_seconds: float = 0.25) -> None:
        """Best-effort recursive deletion with retries for Windows file locks."""
        if not path.exists():
            return

        for attempt in range(1, attempts + 1):
            try:
                await asyncio.to_thread(shutil.rmtree, path, onerror=on_rm_error)
            except Exception as e:
                logger.warning(
                    "temp_cleanup_attempt_failed",
                    path=str(path),
                    attempt=attempt,
                    error=str(e),
                )

            if not path.exists():
                return

            if attempt < attempts:
                await asyncio.sleep(delay_seconds)

        if path.exists():
            raise RepoCloneError(
                f"Could not clean temporary directory: {path}. "
                "Close apps using repository files and retry."
            )

    async def load_repo(self, repo_url: str, branch: Optional[str] = None) -> RepoInfo:
        """
        Clone a repository from GitHub URL or link to local path.

        Args:
            repo_url: GitHub URL or local path
            branch: Optional branch name (default: default branch)

        Returns:
            RepoInfo with repository details

        Raises:
            RepoCloneError: If cloning fails
            RepoTooLargeError: If repo exceeds size limit
        """
        logger.info("loading_repo", repo_url=repo_url, branch=branch)

        # Check if it's a local path
        if os.path.isdir(repo_url):
            return await self._load_local_repo(repo_url)

        # Parse GitHub URL
        try:
            owner, repo_name = self._parse_github_url(repo_url)
        except ValueError as e:
            raise RepoCloneError(str(e))

        # Clone the repository
        return await self._clone_github_repo(repo_url, owner, repo_name, branch)

    async def _load_local_repo(self, local_path: str) -> RepoInfo:
        """Load a local repository."""
        path = Path(local_path)

        if not path.exists():
            raise RepoCloneError(f"Local path does not exist: {local_path}")

        # Get git info if available (run in thread to avoid blocking event loop)
        git_dir = path / ".git"
        if git_dir.exists():
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["git", "rev-parse", "HEAD"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    stdin=subprocess.DEVNULL,
                )
                commit_hash = (
                    result.stdout.strip()[:8] if result.returncode == 0 else "local"
                )

                result = await asyncio.to_thread(
                    subprocess.run,
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    stdin=subprocess.DEVNULL,
                )
                branch = result.stdout.strip() if result.returncode == 0 else "local"
            except Exception:
                commit_hash = "local"
                branch = "local"
        else:
            commit_hash = "local"
            branch = "local"

        repo_name = path.name
        repo_id = self._generate_repo_id(repo_name, commit_hash)

        # Scan for stats
        stats = await self._scan_repo_stats(path)

        repo_info = RepoInfo(
            repo_id=repo_id,
            repo_name=repo_name,
            repo_url=local_path,
            commit_hash=commit_hash,
            branch=branch,
            local_path=str(path),
            stats=stats,
        )

        self._repos[repo_id] = repo_info
        self._save_registry()  # Persist to disk
        logger.info("loaded_local_repo", repo_id=repo_id, repo_name=repo_name)

        return repo_info

    async def _clone_github_repo(
        self, repo_url: str, owner: str, repo_name: str, branch: Optional[str]
    ) -> RepoInfo:
        """Clone a GitHub repository."""

        # First, check repo size using git ls-remote (fast, no clone needed)
        # This is a rough check; actual clone might be smaller due to --depth 1

        # Prepare clone directory
        temp_name = f"{owner}_{repo_name}"

        # Build clone command
        clone_cmd = [
            "git",
            "-c",
            "http.sslBackend=openssl",
            "clone",
            "--depth",
            "1",
            "--single-branch",
            "--no-tags",
            "--filter=blob:none",
        ]
        if branch:
            clone_cmd.extend(["--branch", branch])

        # Clone to temp location first (unique path avoids stale-dir collisions on retries)
        temp_suffix = f"{int(time.time())}_{uuid4().hex[:8]}"
        clone_temp_root = Path(tempfile.gettempdir()) / "repopilot_clone_tmp"
        clone_temp_root.mkdir(parents=True, exist_ok=True)
        temp_path = clone_temp_root / f"_temp_{temp_name}_{temp_suffix}"

        # Best-effort cleanup of stale temp directories from previous failed attempts.
        # Only remove old directories to avoid racing with concurrent clone requests.
        stale_prefix = f"_temp_{temp_name}_"
        stale_cutoff_seconds = 15 * 60
        now_ts = time.time()
        for stale_dir in clone_temp_root.glob(f"{stale_prefix}*"):
            if stale_dir == temp_path:
                continue
            try:
                age_seconds = now_ts - stale_dir.stat().st_mtime
            except OSError:
                continue
            if age_seconds < stale_cutoff_seconds:
                continue
            try:
                await self._safe_remove_tree(stale_dir, attempts=2)
            except Exception as e:
                logger.warning("stale_temp_cleanup_failed", path=str(stale_dir), error=str(e))

        clone_cmd.extend([repo_url, str(temp_path)])

        logger.info("cloning_repo", cmd=" ".join(clone_cmd))
        git_env = os.environ.copy()
        for proxy_key in (
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "no_proxy",
            "NO_PROXY",
        ):
            git_env.pop(proxy_key, None)

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=settings.clone_timeout_seconds,
                stdin=subprocess.DEVNULL,
                env=git_env,
            )

            if result.returncode != 0:
                raise RepoCloneError(f"Git clone failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            await self._safe_remove_tree(temp_path, attempts=4)
            raise RepoCloneError(
                f"Clone timed out after {settings.clone_timeout_seconds}s. "
                "Try again or increase CLONE_TIMEOUT_SECONDS in .env."
            )
        except RepoCloneError:
            raise
        except Exception as e:
            await self._safe_remove_tree(temp_path, attempts=4)
            raise RepoCloneError(f"Clone failed: {str(e)}")

        # Get commit hash
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "HEAD"],
                cwd=temp_path,
                capture_output=True,
                text=True,
                timeout=10,
                stdin=subprocess.DEVNULL,
            )
            commit_hash = result.stdout.strip()
        except Exception:
            commit_hash = "unknown"

        # Get actual branch name
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=temp_path,
                capture_output=True,
                text=True,
                timeout=10,
                stdin=subprocess.DEVNULL,
            )
            actual_branch = result.stdout.strip()
        except Exception:
            actual_branch = branch or "main"

        # Move to final location: data/<repo_name>/<commit_hash>/
        final_path = settings.data_dir / repo_name / commit_hash[:8]
        needs_population = not final_path.exists()
        if final_path.exists():
            existing_stats = await self._scan_repo_stats(final_path)
            if existing_stats.total_files > 0:
                # Already have this version with source files, clean up temp
                try:
                    await self._safe_remove_tree(temp_path, attempts=4)
                except Exception:
                    pass
                logger.info("repo_already_exists", path=str(final_path))
            else:
                logger.warning("repo_exists_but_empty", path=str(final_path))
                await self._safe_remove_tree(final_path, attempts=4)
                needs_population = True

        if needs_population:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                # Fast path: move directory in one operation when possible.
                await asyncio.to_thread(shutil.move, str(temp_path), str(final_path))
            except Exception as move_error:
                logger.warning("move_failed_fallback_copy", error=str(move_error))
                try:
                    if final_path.exists():
                        existing_stats = await self._scan_repo_stats(final_path)
                        if existing_stats.total_files > 0:
                            # Another concurrent request likely populated it first.
                            await self._safe_remove_tree(temp_path, attempts=3)
                            logger.info("repo_already_populated_after_move_race", path=str(final_path))
                            needs_population = False
                        else:
                            await self._safe_remove_tree(final_path, attempts=4)

                    if needs_population:
                        # Copy without .git to reduce payload and avoid lock contention.
                        def ignore_git(directory, files):
                            return [".git"] if ".git" in files else []

                        await asyncio.to_thread(
                            shutil.copytree, str(temp_path), str(final_path), ignore=ignore_git
                        )
                        await self._safe_remove_tree(temp_path, attempts=4)
                except Exception as copy_error:
                    logger.error("copy_failed", error=str(copy_error))
                    try:
                        await self._safe_remove_tree(temp_path, attempts=2)
                    except Exception:
                        pass
                    raise RepoCloneError(f"Failed to move repo: {copy_error}")

        # Drop git metadata once mirrored locally; this reduces disk IO and scan time.
        git_dir = final_path / ".git"
        if git_dir.exists():
            try:
                await self._safe_remove_tree(git_dir, attempts=3)
            except Exception as e:
                logger.warning("git_metadata_cleanup_failed", path=str(git_dir), error=str(e))

        # Scan for stats
        stats = await self._scan_repo_stats(final_path)
        size_mb = stats.total_size_bytes / (1024 * 1024)

        if size_mb > settings.max_repo_size_mb:
            try:
                await self._safe_remove_tree(final_path, attempts=4)
            except Exception:
                pass
            raise RepoTooLargeError(
                f"Repository is {size_mb:.1f}MB, exceeds limit of {settings.max_repo_size_mb}MB. "
                "Increase MAX_REPO_SIZE_MB in .env and restart backend."
            )

        # Check file count
        if stats.total_files > settings.max_files:
            try:
                await self._safe_remove_tree(final_path, attempts=4)
            except Exception:
                pass
            raise RepoTooLargeError(
                f"Repository has {stats.total_files} files, exceeds limit of {settings.max_files}. "
                "Increase MAX_FILES in .env and restart backend."
            )

        repo_id = self._generate_repo_id(repo_name, commit_hash)

        repo_info = RepoInfo(
            repo_id=repo_id,
            repo_name=repo_name,
            repo_url=repo_url,
            commit_hash=commit_hash,
            branch=actual_branch,
            local_path=str(final_path),
            stats=stats,
        )

        self._repos[repo_id] = repo_info
        self._save_registry()  # Persist to disk

        logger.info(
            "cloned_repo",
            repo_id=repo_id,
            repo_name=repo_name,
            commit=commit_hash[:8],
            files=stats.total_files,
            size_mb=f"{size_mb:.2f}",
        )

        return repo_info

    async def _scan_repo_stats(self, repo_path: Path) -> RepoStats:
        """Scan repository and gather statistics."""

        def _scan():
            total_files = 0
            total_size = 0
            languages: dict[str, int] = {}

            for file_path, _, ext in self._iter_candidate_files(repo_path):
                total_files += 1
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    continue

                # Track language by extension
                lang = ext.lstrip(".")
                languages[lang] = languages.get(lang, 0) + 1

            return RepoStats(
                total_files=total_files,
                total_size_bytes=total_size,
                languages=languages,
            )

        return await asyncio.to_thread(_scan)

    def get_repo(self, repo_id: str) -> Optional[RepoInfo]:
        """Get repository info by ID."""
        return self._repos.get(repo_id)

    def update_repo(self, repo_id: str, persist: bool = True, **updates):
        """Update repo info and optionally persist."""
        if repo_id in self._repos:
            for key, value in updates.items():
                if hasattr(self._repos[repo_id], key):
                    setattr(self._repos[repo_id], key, value)
            if persist:
                self._save_registry()

    def get_repo_path(self, repo_id: str) -> Optional[Path]:
        """Get local path for a repository."""
        repo = self._repos.get(repo_id)
        if repo:
            return Path(repo.local_path)
        return None

    async def list_files(self, repo_id: str) -> list[dict]:
        """
        List all eligible files in a repository.

        Returns list of dicts with: file_path, size, language, estimated_tokens
        """
        repo = self._repos.get(repo_id)
        if not repo:
            raise RepoManagerError(f"Repository not found: {repo_id}")

        repo_path = Path(repo.local_path)

        def _list():
            files = []
            for file_path, relative_path, ext in self._iter_candidate_files(repo_path):
                try:
                    size = file_path.stat().st_size

                    # Rough token estimate (1 token ~ 4 chars)
                    estimated_tokens = size // 4

                    files.append(
                        {
                            "file_path": relative_path,
                            "size": size,
                            "language": ext.lstrip(".")
                            if ext
                            else file_path.name.lower(),
                            "estimated_tokens": estimated_tokens,
                        }
                    )
                except OSError:
                    continue
            return files

        return await asyncio.to_thread(_list)

    async def get_file_content(self, repo_id: str, file_path: str) -> str:
        """Read content of a specific file."""
        repo = self._repos.get(repo_id)
        if not repo:
            raise RepoManagerError(f"Repository not found: {repo_id}")

        full_path = Path(repo.local_path) / file_path

        if not full_path.exists():
            raise RepoManagerError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise RepoManagerError(f"Not a file: {file_path}")

        def _read() -> str:
            return full_path.read_text(encoding="utf-8", errors="replace")

        try:
            return await asyncio.to_thread(_read)
        except Exception as e:
            raise RepoManagerError(f"Could not read file: {e}")


# Global instance
repo_manager = RepoManager()
