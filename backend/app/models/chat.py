"""
Chat and QA models.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class Citation(BaseModel):
    """Citation for a grounded answer."""
    file_path: str
    line_range: str
    snippet: str
    why: Optional[str] = None


class ChatRequest(BaseModel):
    """Request to ask a question."""
    repo_id: str
    question: str
    decompose: bool = False


class AnswerConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ChatResponse(BaseModel):
    """Grounded answer response."""
    answer: str
    citations: List[Citation]
    confidence: AnswerConfidence
    assumptions: List[str] = Field(default_factory=list)
    subquestions: Optional[List[str]] = None
