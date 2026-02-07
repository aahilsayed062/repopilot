"""
RepoManager - Handles repository cloning, scanning, and filtering.
"""

import os
import re
import shutil
import subprocess
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
import hashlib

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
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".rb",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt", ".scala",
        ".php", ".pl", ".r", ".m", ".mm", ".lua", ".sh", ".bash", ".zsh",
        ".ps1", ".psm1", ".bat", ".cmd",
        # Web
        ".html", ".css", ".scss", ".sass", ".less", ".vue", ".svelte",
        # Config
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".xml", ".env.example", ".env.sample",
        # Docs
        ".md", ".rst", ".txt", ".adoc",
        # Data
        ".sql", ".graphql", ".gql",
        # Other
        ".dockerfile", ".gitignore", ".gitattributes",
    }
    
    # Directories to exclude
    EXCLUDED_DIRS = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
        "dist", "build", "out", "target", ".next", ".nuxt",
        "coverage", ".pytest_cache", ".mypy_cache", ".tox",
        "vendor", "bower_components", "jspm_packages",
        ".idea", ".vscode", ".vs", "*.egg-info",
    }
    
    # Files to exclude
    EXCLUDED_FILES = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "Cargo.lock", "Gemfile.lock", "poetry.lock",
        ".DS_Store", "Thumbs.db",
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
                    self._repos[repo_id] = RepoInfo(**info)
                    logger.debug("recovered_repo", repo_id=repo_id)
                else:
                    logger.warning("repo_path_missing", repo_id=repo_id, path=local_path)
            
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
        https_match = re.match(r"https://github\.com/([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?$", url)
        if https_match:
            return https_match.group(1), https_match.group(2)
        
        # SSH format: git@github.com:owner/repo.git
        ssh_match = re.match(r"git@github\.com:([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?$", url)
        if ssh_match:
            return ssh_match.group(1), ssh_match.group(2)
        
        raise ValueError(f"Could not parse GitHub URL: {url}")
    
    def _generate_repo_id(self, repo_name: str, commit_hash: str) -> str:
        """Generate unique repo ID from name and commit."""
        combined = f"{repo_name}:{commit_hash[:8]}"
        return hashlib.sha256(combined.encode()).hexdigest()[:12]
    
    async def load_repo(
        self,
        repo_url: str,
        branch: Optional[str] = None
    ) -> RepoInfo:
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
        
        # Get git info if available
        git_dir = path / ".git"
        if git_dir.exists():
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=path,
                    capture_output=True,
                    text=True
                )
                commit_hash = result.stdout.strip()[:8] if result.returncode == 0 else "local"
                
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=path,
                    capture_output=True,
                    text=True
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
            stats=stats
        )
        
        self._repos[repo_id] = repo_info
        self._save_registry()  # Persist to disk
        logger.info("loaded_local_repo", repo_id=repo_id, repo_name=repo_name)
        
        return repo_info
    
    async def _clone_github_repo(
        self,
        repo_url: str,
        owner: str,
        repo_name: str,
        branch: Optional[str]
    ) -> RepoInfo:
        """Clone a GitHub repository."""
        
        # First, check repo size using git ls-remote (fast, no clone needed)
        # This is a rough check; actual clone might be smaller due to --depth 1
        
        # Prepare clone directory
        temp_name = f"{owner}_{repo_name}"
        
        # Build clone command
        clone_cmd = ["git", "clone", "--depth", "1"]
        if branch:
            clone_cmd.extend(["--branch", branch])
        
        # Clone to temp location first
        temp_path = settings.data_dir / f"_temp_{temp_name}"
        if temp_path.exists():
            shutil.rmtree(temp_path, onerror=on_rm_error)
        
        clone_cmd.extend([repo_url, str(temp_path)])
        
        logger.info("cloning_repo", cmd=" ".join(clone_cmd))
        
        try:
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode != 0:
                raise RepoCloneError(f"Git clone failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            if temp_path.exists():
                shutil.rmtree(temp_path, onerror=on_rm_error)
            raise RepoCloneError("Clone timeout - repository may be too large")
        except Exception as e:
            if temp_path.exists():
                shutil.rmtree(temp_path, onerror=on_rm_error)
            raise RepoCloneError(f"Clone failed: {str(e)}")
        
        # Get commit hash
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=temp_path,
                capture_output=True,
                text=True
            )
            commit_hash = result.stdout.strip()
        except Exception:
            commit_hash = "unknown"
        
        # Get actual branch name
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=temp_path,
                capture_output=True,
                text=True
            )
            actual_branch = result.stdout.strip()
        except Exception:
            actual_branch = branch or "main"
        
        # Move to final location: data/<repo_name>/<commit_hash>/
        final_path = settings.data_dir / repo_name / commit_hash[:8]
        if final_path.exists():
            # Already have this version, clean up temp
            try:
                shutil.rmtree(temp_path, onerror=on_rm_error)
            except Exception:
                pass
            logger.info("repo_already_exists", path=str(final_path))
        else:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                # Copy without .git to avoid Windows file locking issues
                def ignore_git(directory, files):
                    return ['.git'] if '.git' in files else []
                
                shutil.copytree(str(temp_path), str(final_path), ignore=ignore_git)
                # Try to clean up temp dir
                shutil.rmtree(temp_path, onerror=on_rm_error)
            except Exception as e:
                logger.error("copy_failed", error=str(e))
                # If copy fails, try move as fallback
                try:
                    if final_path.exists():
                        shutil.rmtree(final_path, ignore_errors=True)
                    shutil.move(str(temp_path), str(final_path))
                except Exception as move_err:
                    logger.error("move_failed", error=str(move_err))
                    shutil.rmtree(temp_path, ignore_errors=True)
                    raise RepoCloneError(f"Failed to move repo: {move_err}")
        
        # Check size (excluding .git)
        total_size = 0
        for f in final_path.rglob("*"):
            if f.is_file() and ".git" not in f.parts:
                try:
                    total_size += f.stat().st_size
                except (OSError, PermissionError):
                    continue
        size_mb = total_size / (1024 * 1024)
        
        if size_mb > settings.max_repo_size_mb:
            shutil.rmtree(final_path, ignore_errors=True)
            raise RepoTooLargeError(
                f"Repository is {size_mb:.1f}MB, exceeds limit of {settings.max_repo_size_mb}MB"
            )
        
        # Scan for stats
        stats = await self._scan_repo_stats(final_path)
        
        # Check file count
        if stats.total_files > settings.max_files:
            raise RepoTooLargeError(
                f"Repository has {stats.total_files} files, exceeds limit of {settings.max_files}"
            )
        
        repo_id = self._generate_repo_id(repo_name, commit_hash)
        
        repo_info = RepoInfo(
            repo_id=repo_id,
            repo_name=repo_name,
            repo_url=repo_url,
            commit_hash=commit_hash,
            branch=actual_branch,
            local_path=str(final_path),
            stats=stats
        )
        
        self._repos[repo_id] = repo_info
        self._save_registry()  # Persist to disk
        
        logger.info(
            "cloned_repo",
            repo_id=repo_id,
            repo_name=repo_name,
            commit=commit_hash[:8],
            files=stats.total_files,
            size_mb=f"{size_mb:.2f}"
        )
        
        return repo_info
    
    async def _scan_repo_stats(self, repo_path: Path) -> RepoStats:
        """Scan repository and gather statistics."""
        total_files = 0
        total_size = 0
        languages: dict[str, int] = {}
        
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Check if in excluded directory
            if any(excl in file_path.parts for excl in self.EXCLUDED_DIRS):
                continue
            
            # Check if excluded file
            if file_path.name in self.EXCLUDED_FILES:
                continue
            
            # Check extension
            ext = file_path.suffix.lower()
            if ext not in self.INCLUDED_EXTENSIONS:
                # Also check for files without extension
                if file_path.name.lower() in {"dockerfile", "makefile", "rakefile", "gemfile"}:
                    ext = f".{file_path.name.lower()}"
                else:
                    continue
            
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
            languages=languages
        )
    
    def get_repo(self, repo_id: str) -> Optional[RepoInfo]:
        """Get repository info by ID."""
        return self._repos.get(repo_id)
    
    def update_repo(self, repo_id: str, **updates):
        """Update repo info and persist."""
        if repo_id in self._repos:
            for key, value in updates.items():
                if hasattr(self._repos[repo_id], key):
                    setattr(self._repos[repo_id], key, value)
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
        files = []
        
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Check if in excluded directory
            if any(excl in file_path.parts for excl in self.EXCLUDED_DIRS):
                continue
            
            # Check if excluded file
            if file_path.name in self.EXCLUDED_FILES:
                continue
            
            # Check extension
            ext = file_path.suffix.lower()
            if ext not in self.INCLUDED_EXTENSIONS:
                if file_path.name.lower() not in {"dockerfile", "makefile", "rakefile", "gemfile"}:
                    continue
            
            try:
                size = file_path.stat().st_size
                relative_path = file_path.relative_to(repo_path)
                
                # Rough token estimate (1 token ≈ 4 chars)
                estimated_tokens = size // 4
                
                files.append({
                    "file_path": str(relative_path),
                    "size": size,
                    "language": ext.lstrip(".") if ext else file_path.name.lower(),
                    "estimated_tokens": estimated_tokens
                })
            except OSError:
                continue
        
        return files
    
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
        
        try:
            return full_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise RepoManagerError(f"Could not read file: {e}")


# Global instance
repo_manager = RepoManager()
