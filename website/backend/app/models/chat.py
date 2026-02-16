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


class ChatTurn(BaseModel):
    """Single conversation turn used for short-term context memory."""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Request to ask a question."""
    repo_id: str
    question: str
    decompose: bool = False
    chat_history: List[ChatTurn] = Field(default_factory=list)
    context_file_hints: List[str] = Field(default_factory=list)


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
    # Round 2 fields
    routing_decision: Optional[str] = None
    routing_reasoning: Optional[str] = None
    agents_used: List[str] = Field(default_factory=list)
    agents_skipped: List[str] = Field(default_factory=list)
