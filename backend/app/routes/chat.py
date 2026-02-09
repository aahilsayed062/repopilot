"""
Chat API endpoints.
"""

import asyncio
import re
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.chat import ChatRequest, ChatResponse, AnswerConfidence
from app.models.chunk import Chunk
from app.services.retriever import retriever
from app.services.answerer import answerer
from app.services.generator import generator, CodeGenerationRequest, GenerationResponse
from app.services.planner import planner
from app.services.test_generator import test_generator
from app.services.repo_manager import repo_manager
from app.services.chunker import chunker
from app.utils.logger import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


CASUAL_PATTERNS = [
    r"^\s*(hi|hello|hey|hey man|yo|sup|hola)\s*[!.]*\s*$",
    r"^\s*(good morning|good afternoon|good evening)\s*[!.]*\s*$",
    r"^\s*(thanks|thank you|thx)\s*[!.]*\s*$",
    r"^\s*(how are you|what'?s up|who are you)\s*[?.!]*\s*$",
]

PATH_CANDIDATE_RE = re.compile(r"([A-Za-z0-9_\-./]+\.[A-Za-z0-9_]+)")
HISTORY_TURN_LIMIT = 5
SHORT_FOLLOW_UP_MAX_WORDS = 6
SHORT_FOLLOW_UP_PATTERNS = (
    "how to fix",
    "how fix",
    "fix this",
    "fix it",
    "what fix",
    "why this",
    "how so",
    "and then",
    "what next",
)


def _is_casual_message(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q:
        return False

    code_markers = [
        "file", "function", "class", "module", "endpoint", "api", "bug",
        "error", "stack", "trace", "index", "repository", "repo", "where",
        "why", "how does", "implement", "architecture", "dependency",
    ]
    if any(marker in q for marker in code_markers):
        return False

    if len(q.split()) > 8:
        return False

    return any(re.match(pattern, q) for pattern in CASUAL_PATTERNS)


def _build_casual_response(question: str) -> ChatResponse:
    q = (question or "").strip().lower()
    if "thank" in q or "thx" in q:
        text = (
            "You’re welcome. I’m ready when you want to dive into the code.\n\n"
            "Try asking something like:\n"
            "- `Explain how repository loading works`\n"
            "- `Where is indexing progress computed?`\n"
            "- `Show potential performance bottlenecks`"
        )
    elif "how are you" in q or "what's up" in q or "whats up" in q:
        text = (
            "Doing well and ready to help. If you want, I can inspect architecture, "
            "trace execution flow, or debug a specific error in your repo."
        )
    else:
        text = (
            "Hey. I’m here and ready.\n\n"
            "Ask me anything about your repository and I’ll answer with concrete "
            "code references."
        )

    return ChatResponse(
        answer=text,
        citations=[],
        confidence=AnswerConfidence.LOW,
        assumptions=["Social/greeting message detected; no code evidence required."],
    )


def _extract_path_candidates(question: str) -> List[str]:
    return [
        m.group(1).strip().strip("`'\"")
        for m in PATH_CANDIDATE_RE.finditer(question or "")
    ]


def _is_short_follow_up(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q:
        return False
    if _extract_path_candidates(q):
        return False
    words = [w for w in re.split(r"\s+", q) if w]
    if len(words) <= SHORT_FOLLOW_UP_MAX_WORDS:
        return True
    return any(pattern in q for pattern in SHORT_FOLLOW_UP_PATTERNS)


def _format_recent_history(request: ChatRequest, limit: int = HISTORY_TURN_LIMIT) -> str:
    """Build compact conversation context from the most recent turns."""
    history = request.chat_history or []
    if not history:
        return ""

    normalized: List[str] = []
    for turn in history[-limit:]:
        role = (turn.role or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = (turn.content or "").strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        normalized.append(f"{label}: {content}")
    return "\n".join(normalized)


async def _retrieve_path_hint_chunks(repo_id: str, question: str) -> List[Chunk]:
    """
    If the question includes a file path-like token, pull chunks directly from that file.
    This improves precision and latency for file-specific questions.
    """
    candidates = _extract_path_candidates(question)
    if not candidates:
        return []

    try:
        files = await repo_manager.list_files(repo_id)
    except Exception:
        return []

    path_index = {f["file_path"].lower(): f["file_path"] for f in files}
    selected_paths: List[str] = []

    for candidate in candidates:
        c = candidate.lower().replace("\\", "/")
        if c in path_index:
            selected_paths.append(path_index[c])
            continue
        for existing in path_index:
            if existing.endswith("/" + c):
                selected_paths.append(path_index[existing])
                break

    deduped = []
    seen = set()
    for p in selected_paths:
        if p not in seen:
            deduped.append(p)
            seen.add(p)

    direct_chunks: List[Chunk] = []
    for file_path in deduped[:2]:
        try:
            content = await repo_manager.get_file_content(repo_id, file_path)
            direct_chunks.extend(chunker.chunk_file(content, repo_id, file_path)[:3])
        except Exception:
            continue

    return direct_chunks


async def _retrieve_context_hint_chunks(repo_id: str, file_hints: List[str]) -> List[Chunk]:
    """
    Pull direct chunks from context-provided file hints (typically prior assistant citations).
    """
    if not file_hints:
        return []

    normalized = []
    seen = set()
    for hint in file_hints:
        path = str(hint or "").strip().replace("\\", "/")
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)

    direct_chunks: List[Chunk] = []
    for file_path in normalized[:3]:
        try:
            content = await repo_manager.get_file_content(repo_id, file_path)
            direct_chunks.extend(chunker.chunk_file(content, repo_id, file_path)[:2])
        except Exception:
            continue
    return direct_chunks


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
        if _is_casual_message(request.question):
            return _build_casual_response(request.question)

        path_candidates = _extract_path_candidates(request.question)
        path_hint_chunks = await _retrieve_path_hint_chunks(request.repo_id, request.question)
        context_hint_chunks = await _retrieve_context_hint_chunks(
            request.repo_id, request.context_file_hints
        )
        if path_candidates and not path_hint_chunks:
            return ChatResponse(
                answer=(
                    "## Direct Answer\n"
                    "I could not find the referenced file path in this repository.\n\n"
                    "## Evidence\n"
                    f"- Requested path hint(s): {', '.join(path_candidates[:3])}\n"
                    "- No matching indexed file path was found.\n\n"
                    "## Next Steps\n"
                    "- Check the exact path and spelling.\n"
                    "- Ask with a nearby known file path if this file was renamed."
                ),
                citations=[],
                confidence=AnswerConfidence.LOW,
                assumptions=["Referenced file path was not found in repository file list."],
            )

        recent_context = _format_recent_history(request)
        retrieval_seed = request.question.strip()
        if recent_context:
            retrieval_seed = (
                f"Current question: {request.question.strip()}\n"
                f"Recent conversation:\n{recent_context}"
            )
        if request.context_file_hints:
            retrieval_seed += (
                "\nPrior cited files that are likely relevant:\n"
                + "\n".join(f"- {p}" for p in request.context_file_hints[:4])
            )

        # 1. Decomposition (only when likely beneficial)
        sub_questions = None
        if request.decompose or planner.should_decompose(request.question):
            try:
                sub_questions = await asyncio.wait_for(
                    planner.decompose(request.question), timeout=4.5
                )
            except Exception:
                sub_questions = None

        is_short_follow_up = _is_short_follow_up(request.question)
        search_queries = sub_questions if sub_questions else [retrieval_seed]
        search_queries = [q.strip() for q in search_queries if q and q.strip()][:2]
        if not search_queries:
            search_queries = [retrieval_seed]
        if is_short_follow_up and recent_context:
            search_queries.insert(
                0,
                (
                    f"Follow-up question: {request.question.strip()}\n"
                    f"Resolve references using recent conversation:\n{recent_context}"
                ),
            )
        if recent_context and sub_questions:
            search_queries = [
                f"{q}\nRelated recent conversation:\n{recent_context}"
                for q in search_queries
            ]
        retrieval_k = 6 if is_short_follow_up else 4

        # 2. Retrieve in parallel
        retrievals = await asyncio.gather(
            *[
                retriever.retrieve(repo_id=request.repo_id, query=q, k=retrieval_k)
                for q in search_queries
            ],
            return_exceptions=True,
        )
        all_chunks = []
        all_chunks.extend(path_hint_chunks)
        all_chunks.extend(context_hint_chunks)
        for result in retrievals:
            if isinstance(result, Exception):
                continue
            all_chunks.extend(result)
            
        # 3. Deduplicate chunks
        seen_ids = set()
        unique_chunks = []
        for c in all_chunks:
            if c.metadata.chunk_id not in seen_ids:
                unique_chunks.append(c)
                seen_ids.add(c.metadata.chunk_id)

        # 4. Answer with bounded context
        response = await answerer.answer(
            query=request.question,
            chunks=unique_chunks[:6],
            conversation_context=recent_context,
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
        return await generator.generate(
            request.repo_id,
            request.request,
            chat_history=request.chat_history,
        )
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

