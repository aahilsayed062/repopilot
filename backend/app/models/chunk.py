"""
Chunking models.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ChunkMetadata(BaseModel):
    """Metadata for a code/doc chunk."""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    repo_id: str = Field(..., description="Parent repository ID")
    file_path: str = Field(..., description="Relative file path")
    start_line: int = Field(..., description="Starting line number (1-indexed)")
    end_line: int = Field(..., description="Ending line number (1-indexed)")
    language: str = Field(default="text", description="Programming language")
    chunk_type: str = Field(default="code", description="Type: code, doc, config")
    token_count: int = Field(default=0, description="Estimated token count")


class Chunk(BaseModel):
    """A chunk of code or documentation with metadata."""
    metadata: ChunkMetadata
    content: str = Field(..., description="Chunk text content")
    
    @property
    def chunk_id(self) -> str:
        return self.metadata.chunk_id
    
    @property
    def file_path(self) -> str:
        return self.metadata.file_path
    
    @property
    def line_range(self) -> str:
        """Human-readable line range."""
        return f"L{self.metadata.start_line}-L{self.metadata.end_line}"


class ChunkingStats(BaseModel):
    """Statistics from chunking operation."""
    total_chunks: int = 0
    total_files: int = 0
    total_tokens: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_language: dict[str, int] = Field(default_factory=dict)
