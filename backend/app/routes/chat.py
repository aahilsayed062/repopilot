"""
Chat API endpoints.
"""

from fastapi import APIRouter, HTTPException

from app.models.chat import ChatRequest, ChatResponse
from app.services.retriever import retriever
from app.services.answerer import answerer
from app.services.generator import generator, CodeGenerationRequest, GenerationResponse
from app.services.planner import planner
from app.utils.logger import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


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
