"""
Analysis models — Request/Response schemas for the /api/analyze endpoint.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
import re


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/analyze."""
    github_url: str = Field(..., description="Public GitHub repository URL")
    branch: Optional[str] = Field(default=None, description="Branch to analyze (auto-detects if not specified)")
    
    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v.endswith(".git"):
            v = v[:-4]
        pattern = r"(?:https?://)?(?:www\.)?github\.com/[^/]+/[^/]+"
        if not re.match(pattern, v):
            raise ValueError("Invalid GitHub URL. Expected format: https://github.com/owner/repo")
        return v


class ComponentInfo(BaseModel):
    """A detected component in the repository."""
    name: str
    path: str
    description: str


class FileNode(BaseModel):
    """Node in the file tree."""
    name: str
    type: str  # "file" or "directory"
    path: Optional[str] = ""
    language: Optional[str] = None
    size: Optional[int] = 0
    children: Optional[List["FileNode"]] = None
    truncated: Optional[bool] = False


class GraphNode(BaseModel):
    """Node in the graph visualization."""
    id: str
    type: str
    name: str
    path: str
    language: Optional[str] = None
    color: str
    size: int = 0
    depth: int = 0
    childCount: int = 0
    complexity: Optional[str] = None
    heatColor: Optional[str] = None


class GraphEdge(BaseModel):
    """Edge in the graph visualization."""
    id: str
    source: str
    target: str


class ComponentHighlight(BaseModel):
    """Component highlighted in the graph."""
    nodeId: str
    name: str
    description: str
    path: str


class DependencyInfo(BaseModel):
    """A parsed dependency."""
    name: str
    version: str
    type: str  # "runtime" or "dev"
    ecosystem: str  # "npm", "pip", "go", "cargo"
    category: Optional[str] = "Other"


class RepoStats(BaseModel):
    """Computed repository statistics."""
    total_files: int
    total_lines: int
    languages: Dict[str, Any]
    languages_pct: Dict[str, float]
    directory_depth: int
    structure_type: str


class AnalyzeResponse(BaseModel):
    """Full response from POST /api/analyze."""
    # Repo identity
    repo_name: str
    branch: str
    
    # LLM architecture analysis
    summary: str
    tech_stack: List[str]
    architecture_pattern: str
    components: List[ComponentInfo]
    entry_points: List[str]
    data_flow: str
    mermaid_diagram: str
    readme_summary: Optional[str] = None
    
    # Computed stats (zero LLM tokens)
    stats: RepoStats
    
    # Visualization data
    file_tree: Dict[str, Any]
    graph: Dict[str, Any]
    
    # Dependencies
    dependency_graph: Dict[str, Any]
    
    # Key files detected
    key_files: List[Dict[str, str]]


# Allow recursive FileNode
FileNode.model_rebuild()
