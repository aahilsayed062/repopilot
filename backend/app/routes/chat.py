"""
Chat API endpoints.
"""

import asyncio
import re
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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
            "You're welcome. I'm ready when you want to dive into the code.\n\n"
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
            "Hey. I'm here and ready.\n\n"
            "Ask me anything about your repository and I'll answer with concrete "
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
class GeneratedCodeContext(BaseModel):
    """Context about code that was just generated (for accurate test targeting)."""
    file_path: str
    content: str

class PyTestRequest(BaseModel):
    """Request for PyTest generation."""
    repo_id: str
    target_file: Optional[str] = None
    target_function: Optional[str] = None
    custom_request: Optional[str] = None
    generated_code: Optional[List[GeneratedCodeContext]] = None


class PyTestResponse(BaseModel):
    """Response containing generated tests."""
    success: bool
    tests: str
    test_file_name: str
    explanation: str
    coverage_notes: List[str]
    source_files: List[str] = []
    error: Optional[str] = None


# ───────────────────────────────────────────────────────────────────
# /ask — Standard Q&A endpoint
# ───────────────────────────────────────────────────────────────────

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

        # 1. Decomposition (only when explicitly requested)
        sub_questions = None
        if request.decompose or planner.should_decompose(request.question):
            try:
                sub_questions = await asyncio.wait_for(
                    planner.decompose(request.question), timeout=8.0
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
        # Reduced k for Ollama (smaller context window, faster inference)
        retrieval_k = 4 if is_short_follow_up else 3

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
            chunks=unique_chunks[:4],
            conversation_context=recent_context,
        )
        return response
        
    except Exception as e:
        logger.exception("chat_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_chat(request: ChatRequest):
    """
    Stream a grounded answer using Server-Sent Events (SSE).
    """
    async def event_generator():
        try:
            # 1. Retrieval (simplified version of /ask)
            path_hint_chunks = await _retrieve_path_hint_chunks(request.repo_id, request.question)
            
            # Simple retrieval for speed
            retrieval_k = 4
            chunks = await retriever.retrieve(request.repo_id, request.question, k=retrieval_k)
            
            all_chunks = path_hint_chunks + chunks
            
            # Deduplicate
            seen_ids = set()
            unique_chunks = []
            for c in all_chunks:
                if c.metadata.chunk_id not in seen_ids:
                    unique_chunks.append(c)
                    seen_ids.add(c.metadata.chunk_id)
            
            # Yield retrieval status
            # yield f"event: status\ndata: Found {len(unique_chunks)} relevant code chunks.\n\n"

            # 2. Stream Answer
            recent_context = _format_recent_history(request)
            
            async for token in answerer.answer_stream(request.question, unique_chunks[:4], recent_context):
                # SSE format: data: <content>\n\n
                # We sanitize newlines for SSE data protocol
                sanitized = token.replace("\n", "\\n")
                yield f"data: {sanitized}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error("stream_failed", error=str(e))
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ───────────────────────────────────────────────────────────────────
# /impact — Risk & Change Impact Analysis (Feature 4)
# ───────────────────────────────────────────────────────────────────

class ImpactRequest(BaseModel):
    repo_id: str
    changed_files: list[str]
    code_changes: str = ""


@router.post("/impact")
async def analyze_impact(request: ImpactRequest):
    """
    Analyze the impact of code changes on the repository.
    Returns risk level, affected files, and recommendations.
    """
    try:
        from app.services.impact_analyzer import impact_analyzer
        report = await impact_analyzer.analyze(
            code_changes=request.code_changes,
            changed_files=request.changed_files,
            repo_id=request.repo_id,
        )
        return report.model_dump()
    except Exception as e:
        logger.exception("impact_analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────────────────────────────────────────
# /evaluate — LLM vs LLM Evaluation Layer (Feature 3)
# ───────────────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    request_text: str
    generated_diffs: list[dict]
    tests_text: str = ""
    context: str = ""


@router.post("/evaluate")
async def evaluate_generation(request: EvaluateRequest):
    """
    Evaluate generated code using Critic-Defender-Controller pipeline.
    """
    try:
        from app.services.evaluator import evaluator
        result = await evaluator.evaluate_generation(
            request_text=request.request_text,
            generated_diffs=request.generated_diffs,
            tests_text=request.tests_text,
            context=request.context,
        )
        return result.model_dump()
    except Exception as e:
        logger.exception("evaluate_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────────────────────────────────────────
# /generate — Code generation
# ───────────────────────────────────────────────────────────────────

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


# ───────────────────────────────────────────────────────────────────
# /pytest — Test generation
# ───────────────────────────────────────────────────────────────────

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
            custom_request=request.custom_request,
            generated_code=[{"file_path": g.file_path, "content": g.content} for g in request.generated_code] if request.generated_code else None
        )
        return PyTestResponse(**result)
    except Exception as e:
        logger.exception("pytest_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────────────────────────────────────────
# Feature 1 (Round 2): Dynamic Multi-Agent Routing — /chat/smart
# Agents can run in parallel, be skipped, or chain based on query.
# ───────────────────────────────────────────────────────────────────

async def _run_explain(request: ChatRequest) -> dict:
    """Run the EXPLAIN pipeline (same logic as /ask)."""
    response = await ask_question(request)
    return {
        "answer": response.answer,
        "citations": [c.model_dump() for c in response.citations],
        "confidence": response.confidence.value,
        "assumptions": response.assumptions,
        "subquestions": response.subquestions,
    }


async def _run_generate(request: ChatRequest) -> dict:
    """Run the GENERATE pipeline (same logic as /generate)."""
    gen_request = CodeGenerationRequest(
        repo_id=request.repo_id,
        request=request.question,
        chat_history=[t.model_dump() for t in (request.chat_history or [])],
    )
    result = await generator.generate(
        gen_request.repo_id,
        gen_request.request,
        chat_history=gen_request.chat_history,
    )
    return result.model_dump()


async def _run_test(request: ChatRequest) -> dict:
    """Run the TEST pipeline (same logic as /pytest)."""
    result = await test_generator.generate_tests(
        repo_id=request.repo_id,
        custom_request=request.question,
    )
    return result


@router.post("/smart")
async def smart_chat(request: ChatRequest):
    """
    Dynamic multi-agent routing endpoint.
    Analyzes the user's query and decides which agents to invoke.
    
    Agents can:
    - Run in parallel (e.g., GENERATE + TEST simultaneously)
    - Be skipped based on routing decision
    - Chain (e.g., DECOMPOSE → EXPLAIN)
    """
    from app.services.agent_router import agent_router, AgentAction
    from app.utils.cache import response_cache
    from app.services.repo_manager import repo_manager as _rm

    try:
        # ── Cache check: return instantly if we have a cached answer ──
        repo_info = _rm.get_repo(request.repo_id)
        commit_hash = repo_info.commit_hash if repo_info else "unknown"

        cached = await response_cache.get_response(
            request.repo_id, request.question, commit_hash,
        )
        if cached is not None:
            cached["_from_cache"] = True
            return cached

        # Step 1: Route the query (check routing cache first)
        cached_routing = await response_cache.get_routing(request.question)
        if cached_routing is not None:
            from app.services.agent_router import RoutingDecision
            decision = RoutingDecision(**cached_routing)
            logger.info("smart_routing_from_cache", primary=decision.primary_action.value)
        else:
            decision = await agent_router.route(request.question)
            # Cache the routing decision for future identical queries
            await response_cache.put_routing(
                request.question, decision.model_dump(),
            )
        logger.info(
            "smart_routing_decision",
            primary=decision.primary_action.value,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
        )

        # Build base result with routing metadata
        result = {
            "routing": decision.model_dump(),
            "agents_used": [decision.primary_action.value],
            "agents_skipped": decision.skip_agents,
        }

        # Step 2: Handle REFUSE immediately
        if decision.primary_action == AgentAction.REFUSE:
            result["answer"] = "I cannot safely process this request."
            result["confidence"] = "low"
            return result

        # Step 3: Dispatch to agents based on routing decision
        # Feature 3 constraint: evaluation must run BEFORE test generation.
        # So we split into two phases:
        #   Phase A: EXPLAIN + GENERATE (can run in parallel)
        #   Phase B: EVALUATE generated code (if any)
        #   Phase C: TEST (only if evaluation passes or no generation occurred)

        phase_a_tasks = {}
        wants_test = False

        if decision.primary_action == AgentAction.EXPLAIN or AgentAction.EXPLAIN in decision.secondary_actions:
            phase_a_tasks["explain"] = _run_explain(request)
        if decision.primary_action == AgentAction.GENERATE or AgentAction.GENERATE in decision.secondary_actions:
            phase_a_tasks["generate"] = _run_generate(request)
        if decision.primary_action == AgentAction.TEST or AgentAction.TEST in decision.secondary_actions or AgentAction.TEST in decision.parallel_agents:
            wants_test = True
        if decision.primary_action == AgentAction.DECOMPOSE or decision.should_decompose:
            # Decompose then explain — pass decompose=True to trigger planner
            phase_a_tasks["explain"] = _run_explain(
                ChatRequest(
                    repo_id=request.repo_id,
                    question=request.question,
                    decompose=True,
                    chat_history=request.chat_history,
                    context_file_hints=request.context_file_hints,
                )
            )

        # Fallback: if no tasks were dispatched, default to explain
        if not phase_a_tasks and not wants_test:
            phase_a_tasks["explain"] = _run_explain(request)

        # Phase A: Run explain + generate concurrently
        if phase_a_tasks:
            keys_a = list(phase_a_tasks.keys())
            results_a = await asyncio.gather(*phase_a_tasks.values(), return_exceptions=True)
            for key, res in zip(keys_a, results_a):
                if isinstance(res, Exception):
                    logger.error("agent_task_failed", agent=key, error=str(res))
                    result[key] = {"error": str(res)}
                else:
                    result[key] = res

        # Phase B+C (overlapped): Run Evaluation and Test SPECULATIVELY in parallel.
        # Feature 3 says evaluation must happen "before PyTest generation" — we
        # satisfy this logically: if evaluation returns REQUEST_REVISION we discard
        # the speculative test result.  This saves 8-15 s vs sequential.
        evaluation_allows_test = True
        if "generate" in result and isinstance(result["generate"], dict):
            diffs = result["generate"].get("diffs", [])
            if diffs:
                from app.services.evaluator import evaluator
                eval_context = ""
                if isinstance(result.get("explain"), dict):
                    eval_context = str(result["explain"].get("answer", ""))

                # Build tasks
                eval_coro = evaluator.evaluate_generation(
                    request_text=request.question,
                    generated_diffs=diffs,
                    tests_text=str(result["generate"].get("tests", "")),
                    context=eval_context,
                )

                # Speculative test task (only if routing wanted tests)
                test_coro = _run_test(request) if wants_test else None

                if test_coro is not None:
                    # Run evaluation + test in parallel
                    eval_res, test_res = await asyncio.gather(
                        eval_coro, test_coro, return_exceptions=True,
                    )
                else:
                    eval_res = await eval_coro
                    test_res = None

                # ── Process evaluation result ──
                if isinstance(eval_res, Exception):
                    logger.error("smart_evaluation_failed", error=str(eval_res))
                    result["evaluation"] = {"enabled": False, "error": str(eval_res)}
                else:
                    eval_payload = eval_res.model_dump()
                    result["evaluation"] = eval_payload
                    controller = eval_payload.get("controller", {})
                    eval_decision = str(controller.get("decision", ""))
                    if eval_decision == "REQUEST_REVISION":
                        result["evaluation_action"] = "revision_recommended"
                        evaluation_allows_test = False
                    elif eval_decision == "MERGE_FEEDBACK":
                        improved = controller.get("improved_code_by_file", [])
                        if isinstance(improved, list) and improved:
                            result["evaluation_improved_code"] = improved

                # ── Process test result (discard if evaluation rejected) ──
                if test_res is not None and wants_test:
                    if evaluation_allows_test:
                        if isinstance(test_res, Exception):
                            logger.error("agent_task_failed", agent="test", error=str(test_res))
                            result["test"] = {"error": str(test_res)}
                        else:
                            result["test"] = test_res
                    else:
                        # Evaluation rejected → discard speculative test
                        result["test"] = {
                            "skipped": True,
                            "reason": "Evaluation recommended revision — speculative test discarded.",
                        }
                        result.setdefault("agents_skipped", [])
                        if isinstance(result["agents_skipped"], list):
                            result["agents_skipped"].append("TEST")
            else:
                result["evaluation"] = {
                    "enabled": False,
                    "reason": "No generated diffs available for evaluation.",
                }
        elif wants_test:
            # No generation happened but test was requested
            try:
                test_result = await _run_test(request)
                result["test"] = test_result
            except Exception as test_err:
                logger.error("agent_task_failed", agent="test", error=str(test_err))
                result["test"] = {"error": str(test_err)}

        # Track which agents actually ran
        result["agents_used"] = [decision.primary_action.value] + [
            a.value for a in decision.secondary_actions
        ] + [a.value for a in decision.parallel_agents]
        # Deduplicate
        result["agents_used"] = list(dict.fromkeys(result["agents_used"]))

        # Provide a top-level answer from the primary agent result
        if "explain" in result and isinstance(result["explain"], dict):
            result["answer"] = result["explain"].get("answer", "")
            result["citations"] = result["explain"].get("citations", [])
            result["confidence"] = result["explain"].get("confidence", "medium")
        elif "generate" in result and isinstance(result["generate"], dict):
            result["answer"] = result["generate"].get("plan", "Code generation completed.")
            result["confidence"] = "high"
        else:
            result.setdefault("answer", "Request processed.")
            result.setdefault("confidence", "medium")

        # ── Store result in cache for future identical queries ──
        result["_cache_repo_id"] = request.repo_id  # used for invalidation
        await response_cache.put_response(
            request.repo_id, request.question, commit_hash, result,
        )

        return result

    except Exception as e:
        logger.exception("smart_chat_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────────────────────────────────────────────────
# Feature 2 (Round 2): Iterative PyTest-Driven Refinement — /chat/refine
# ───────────────────────────────────────────────────────────────────

@router.post("/refine")
async def refine_code(request: CodeGenerationRequest):
    """
    Iterative PyTest-driven refinement loop.

    Generates code → generates tests → runs pytest → if fails, refines
    code using the failure output as feedback → repeats (max 4 iterations).

    Uses the same request body as /generate:
    - repo_id: Repository ID
    - request: What to generate
    - chat_history: Previous conversation turns
    """
    from app.services.refinement_loop import refinement_loop

    try:
        result = await refinement_loop.run_refinement(
            repo_id=request.repo_id,
            request=request.request,
            chat_history=request.chat_history,
        )
        return result.model_dump()
    except Exception as e:
        logger.exception("refinement_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
