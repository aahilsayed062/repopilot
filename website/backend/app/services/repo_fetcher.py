"""
Repo Fetcher Service — Clone & scan GitHub repos.

Handles:
- Shallow clone (--depth 1) of public GitHub repos
- Auto-detect default branch
- Timeout protection (60s max)
- Cleanup cloned repos after analysis (temp directory)
"""

import os
import shutil
import subprocess
import tempfile
import asyncio
import re
from pathlib import Path
from typing import Optional, Dict, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Max size limit for cloned repos
MAX_CLONE_SIZE_MB = 100
CLONE_TIMEOUT_SECONDS = 60


def parse_github_url(url: str) -> Dict[str, str]:
    """
    Parse a GitHub URL into owner and repo name.
    Supports: https://github.com/user/repo, github.com/user/repo, etc.
    """
    url = url.strip().rstrip("/")
    # Remove .git suffix
    if url.endswith(".git"):
        url = url[:-4]
    
    # Match github.com/owner/repo
    pattern = r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError(f"Invalid GitHub URL: {url}")
    
    owner = match.group(1)
    repo = match.group(2)
    return {"owner": owner, "repo": repo, "clone_url": f"https://github.com/{owner}/{repo}.git"}


async def clone_repo(github_url: str, branch: Optional[str] = None) -> Dict[str, Any]:
    """
    Shallow clone a GitHub repo into a temp directory.
    Returns the temp directory path plus repo metadata.
    """
    parsed = parse_github_url(github_url)
    clone_url = parsed["clone_url"]
    repo_name = f"{parsed['owner']}/{parsed['repo']}"
    
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix=f"repopilot_{parsed['owner']}_{parsed['repo']}_")
    
    logger.info("cloning_repo", repo=repo_name, target=temp_dir)
    
    try:
        # Build git clone command
        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd += ["--branch", branch]
        cmd += [clone_url, temp_dir]
        
        # Run clone in a thread to avoid blocking the event loop
        # (asyncio.create_subprocess_exec doesn't work on Windows uvicorn)
        def _run_clone():
            return subprocess.run(
                cmd,
                capture_output=True,
                timeout=CLONE_TIMEOUT_SECONDS,
            )
        
        result = await asyncio.to_thread(_run_clone)
        
        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Git clone failed: {error_msg}")
        
        # Check size
        total_size = _get_dir_size(temp_dir)
        if total_size > MAX_CLONE_SIZE_MB * 1024 * 1024:
            cleanup_repo(temp_dir)
            raise ValueError(f"Repository too large: {total_size / (1024*1024):.1f}MB exceeds {MAX_CLONE_SIZE_MB}MB limit")
        
        # Detect branch
        detected_branch = branch
        if not detected_branch:
            try:
                br_result = subprocess.run(
                    ["git", "-C", temp_dir, "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, timeout=10,
                )
                detected_branch = br_result.stdout.decode().strip() or "main"
            except Exception:
                detected_branch = "main"
        
        logger.info("clone_complete", repo=repo_name, size_mb=f"{total_size/(1024*1024):.1f}")
        
        return {
            "temp_dir": temp_dir,
            "owner": parsed["owner"],
            "repo": parsed["repo"],
            "repo_name": repo_name,
            "branch": detected_branch,
            "clone_url": clone_url,
            "size_bytes": total_size,
        }
    
    except subprocess.TimeoutExpired:
        cleanup_repo(temp_dir)
        raise TimeoutError(f"Clone timed out after {CLONE_TIMEOUT_SECONDS}s")
    except Exception as e:
        cleanup_repo(temp_dir)
        raise


def cleanup_repo(temp_dir: str):
    """Remove a cloned repo temp directory."""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("cleanup_complete", path=temp_dir)
    except Exception as e:
        logger.warning("cleanup_failed", path=temp_dir, error=str(e))


def _get_dir_size(path: str) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        # Skip .git
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total
