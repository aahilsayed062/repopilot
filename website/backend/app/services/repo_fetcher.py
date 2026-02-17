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
import zipfile
from io import BytesIO
from typing import Optional, Dict, Any
import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

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
        # Prefer git clone when available; on serverless hosts without git (e.g. Vercel),
        # fall back to GitHub archive download.
        git_available = shutil.which("git") is not None
        if git_available:
            cmd = ["git", "clone", "--depth", "1"]
            if branch:
                cmd += ["--branch", branch]
            cmd += [clone_url, temp_dir]

            def _run_clone():
                return subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=settings.clone_timeout_seconds,
                )

            result = await asyncio.to_thread(_run_clone)
            if result.returncode != 0:
                error_msg = result.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"Git clone failed: {error_msg}")
        else:
            await _download_repo_archive(parsed["owner"], parsed["repo"], branch, temp_dir)
        
        # Check size
        total_size = _get_dir_size(temp_dir)
        if total_size > settings.max_repo_size_mb * 1024 * 1024:
            cleanup_repo(temp_dir)
            raise ValueError(
                f"Repository too large: {total_size / (1024*1024):.1f}MB exceeds {settings.max_repo_size_mb}MB limit"
            )
        
        # Detect branch
        detected_branch = branch
        if not detected_branch and git_available:
            try:
                br_result = subprocess.run(
                    ["git", "-C", temp_dir, "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, timeout=10,
                )
                detected_branch = br_result.stdout.decode().strip() or "main"
            except Exception:
                detected_branch = "main"
        if not detected_branch:
            detected_branch = "default"
        
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
        raise TimeoutError(f"Clone timed out after {settings.clone_timeout_seconds}s")
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


async def _download_repo_archive(owner: str, repo: str, branch: Optional[str], target_dir: str) -> None:
    """Download and extract a GitHub repository archive into target_dir."""
    if branch:
        archive_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{branch}"
    else:
        archive_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoPilot-Website"}
    timeout = httpx.Timeout(settings.clone_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(archive_url, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"Archive download failed ({response.status_code}) for {owner}/{repo}")
        archive_bytes = response.content

    await asyncio.to_thread(_extract_zip_to_target, archive_bytes, target_dir)


def _extract_zip_to_target(archive_bytes: bytes, target_dir: str) -> None:
    """Extract zip archive, flattening the top-level GitHub wrapper directory."""
    with zipfile.ZipFile(BytesIO(archive_bytes)) as zf:
        members = [m for m in zf.namelist() if m and not m.endswith("/")]
        if not members:
            raise RuntimeError("Downloaded repository archive is empty")

        # GitHub archives contain a single root folder like owner-repo-sha/.
        root_prefix = members[0].split("/", 1)[0] + "/"
        for member in members:
            if not member.startswith(root_prefix):
                continue
            relative = member[len(root_prefix):]
            if not relative:
                continue
            output_path = os.path.join(target_dir, relative)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with zf.open(member) as src, open(output_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
