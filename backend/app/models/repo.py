"""
Repository-related Pydantic models.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import re


class RepoLoadRequest(BaseModel):
    """Request to load a repository."""
    repo_url: str = Field(..., description="GitHub URL or local path")
    branch: Optional[str] = Field(default=None, description="Branch to clone (default: default branch)")
    
    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        """Validate GitHub URL or local path format."""
        v = v.strip()
        
        # GitHub URL patterns
        github_patterns = [
            r"^https://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?$",
            r"^git@github\.com:[\w\-\.]+/[\w\-\.]+(?:\.git)?$",
        ]
        
        # Check if it's a valid GitHub URL
        for pattern in github_patterns:
            if re.match(pattern, v):
                return v
        
        # Check if it could be a local path (basic check)
        if "/" in v or "\\" in v:
            return v
            
        raise ValueError("Invalid repository URL. Must be a GitHub URL or local path.")


class RepoStats(BaseModel):
    """Statistics about a loaded repository."""
    total_files: int = 0
    total_size_bytes: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    

class RepoInfo(BaseModel):
    """Information about a loaded repository."""
    repo_id: str = Field(..., description="Unique identifier for this repo version")
    repo_name: str = Field(..., description="Repository name")
    repo_url: str = Field(..., description="Original URL or path")
    commit_hash: str = Field(..., description="Current commit hash")
    branch: str = Field(..., description="Branch name")
    local_path: str = Field(..., description="Local path where repo is stored")
    loaded_at: datetime = Field(default_factory=datetime.utcnow)
    stats: Optional[RepoStats] = None
    indexed: bool = False
    chunk_count: int = 0


class RepoLoadResponse(BaseModel):
    """Response from loading a repository."""
    success: bool
    repo_id: str
    repo_name: str
    commit_hash: str
    stats: RepoStats
    message: str


class RepoStatusResponse(BaseModel):
    """Response for repository status."""
    repo_id: str
    repo_name: str
    exists: bool
    indexed: bool
    stats: Optional[RepoStats] = None
    chunk_count: int = 0
    files: Optional[list[dict]] = None


class RepoIndexRequest(BaseModel):
    """Request to index a repository."""
    repo_id: str = Field(..., description="Repository ID to index")
    force: bool = Field(default=False, description="Force re-indexing even if already indexed")


class RepoIndexResponse(BaseModel):
    """Response from indexing a repository."""
    success: bool
    repo_id: str
    indexed: bool
    chunk_count: int
    message: str
