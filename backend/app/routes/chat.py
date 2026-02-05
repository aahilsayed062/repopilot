"""
Chat API endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.chat import ChatRequest, ChatResponse
from app.services.retriever import retriever
from app.services.answerer import answerer
from app.services.generator import generator, CodeGenerationRequest, GenerationResponse
from app.services.planner import planner
from app.services.test_generator import test_generator
from app.utils.logger import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


# PyTest Generation Models
class PyTestRequest(BaseModel):
    """Request for PyTest generation."""
    repo_id: str
    target_file: Optional[str] = None
    target_function: Optional[str] = None
    custom_request: Optional[str] = None


class PyTestResponse(BaseModel):
    """Response containing generated tests."""
    success: bool
    tests: str
    test_file_name: str
    explanation: str
    coverage_notes: List[str]
    source_files: List[str] = []
    error: Optional[str] = None


@router.post("/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest) -> ChatResponse:
    """
    Ask a question about the repository.
    """
    try:
        # 1. Decomposition (M7)
        sub_questions = await planner.decompose(request.question)
        search_queries = sub_questions if sub_questions else [request.question]
        
        all_chunks = []
        for q in search_queries:
            # 2. Retrieve
            chunks = await retriever.retrieve(
                repo_id=request.repo_id,
                query=q
            )
            all_chunks.extend(chunks)
            
        # Deduplicate chunks
        seen_ids = set()
        unique_chunks = []
        for c in all_chunks:
            if c.metadata.chunk_id not in seen_ids:
                unique_chunks.append(c)
                seen_ids.add(c.metadata.chunk_id)

        # 3. Answer
        # Limit total chunks to 5 to prevent token overflow
        response = await answerer.answer(
            query=request.question,
            chunks=unique_chunks[:5]
        )
        
        return response
        
    except Exception as e:
        logger.exception("chat_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=GenerationResponse)
async def generate_code(request: CodeGenerationRequest) -> GenerationResponse:
    """
    Generate code changes based on request.
    """
    try:
        return await generator.generate(request.repo_id, request.request)
    except Exception as e:
        logger.exception("generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pytest", response_model=PyTestResponse)
async def generate_pytest(request: PyTestRequest) -> PyTestResponse:
    """
    Generate PyTest test cases for repository code.
    
    - If target_file is provided, generates tests for that file
    - If target_function is provided, focuses on that function
    - If custom_request is provided, uses that as guidance
    - Otherwise, generates tests for main functionality
    """
    try:
        result = await test_generator.generate_tests(
            repo_id=request.repo_id,
            target_file=request.target_file,
            target_function=request.target_function,
            custom_request=request.custom_request
        )
        return PyTestResponse(**result)
    except Exception as e:
        logger.exception("pytest_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

