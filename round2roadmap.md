# 🚀 RepoPilot AI — Round 2 Implementation Roadmap (24 Hours)

> **Team**: AlphaByte 3.0 (4 members)
> **Deadline**: ~24 hours from now
> **Current time**: Feb 16, 2026 ~10:00 AM IST
> **Submission by**: Feb 17, 2026 ~10:00 AM IST

---

## ⚠️ Read This First (Team Lead Only)

This roadmap is based on a **line-by-line analysis** of the current codebase. Every file path, every function reference below is **real and verified**. Do NOT skip reading this section.

### Current State Summary

| Component | Status | LOC |
|---|---|---|
| `backend/app/routes/chat.py` | Working — has `/ask`, `/generate`, `/pytest` | 377 |
| `backend/app/services/generator.py` | Working — generates diffs + plan | 335 |
| `backend/app/services/test_generator.py` | Working — generates pytest code (NOT auto-run) | 157 |
| `backend/app/services/planner.py` | Working — decomposes queries (but **invisible** to user) | 73 |
| `backend/app/services/answerer.py` | Working — grounded Q&A with citations | 497 |
| `backend/app/services/retriever.py` | Working — hybrid search | 115 |
| `backend/app/utils/llm.py` | Working — Groq → Gemini → Mock fallback | 214 |
| `frontend/src/app/page.tsx` | Working — full UI | 1245 |
| `vscode-extension/src/chatPanel.ts` | Working — but "Apply Changes" only opens files | 632 |

### What Round 2 Demands (4 Features)

1. **Dynamic Multi-Agent Routing** — Agents don't run in fixed order; system decides flow dynamically
2. **Iterative PyTest-Driven Refinement** — Generate → Run → Fail → Fix → Repeat (3-5 iterations)
3. **LLM vs LLM Evaluation Layer** — Two LLM agents independently review code, controller merges
4. **Risk and Change Impact Analysis** — Report files changed, files indirectly affected, risks

---

## 🔧 Free LLM Strategy (CRITICAL)

We're using **100% free APIs**. Here's the strategy:

| Purpose | Model | Why |
|---|---|---|
| **Fast Chat (Agent A)** | **Groq** — `llama-3.3-70b-versatile` | Free tier, 500+ tok/s, 128k context |
| **Second Opinion (Agent B)** | **Gemini** — `gemini-2.0-flash` | Free tier, different training data = independent review |
| **Embeddings** | **Gemini** — `text-embedding-004` | Already configured, free |
| **Routing Decisions** | **Groq** — `llama-3.3-70b-versatile` | Fast JSON responses for routing |

> **Key insight**: For Feature 3 (LLM vs LLM), we use Groq as Agent A and Gemini as Agent B. Different model families = genuinely independent critique. This is NOT fake diversity — judges will ask.

### `.env` Should Have:
```env
OPENAI_API_KEY=gsk_your_groq_key_here
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_CHAT_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=your_gemini_key_here
GEMINI_CHAT_MODEL=gemini-2.0-flash
```

---

## 👥 Team Assignments

| Member | Feature | New Files | Modified Files |
|---|---|---|---|
| **Member 1 (Lead/Backend)** | Feature 1: Multi-Agent Router | `services/agent_router.py` | `routes/chat.py`, `models/chat.py` |
| **Member 2 (Backend)** | Feature 2: Iterative PyTest Loop | `services/refinement_loop.py` | `routes/chat.py`, `services/test_generator.py` |
| **Member 3 (Backend)** | Feature 3: LLM vs LLM + Feature 4: Risk Analysis | `services/evaluator.py`, `services/impact_analyzer.py` | `utils/llm.py`, `routes/chat.py` |
| **Member 4 (Frontend/Extension)** | UI for all 4 features | — | `frontend/src/app/page.tsx`, `vscode-extension/` |

---

## 📋 Feature 1: Dynamic Multi-Agent Routing

**Owner: Member 1**
**Time: 5-6 hours**
**Concept**: Instead of the user deciding whether to call `/ask` vs `/generate`, the system analyzes the query and decides which agents to invoke (and which to skip).

### What Exists Today
In `routes/chat.py`, the routing is **user-driven**:
- User sends to `/chat/ask` → always runs Planner → Retriever → Answerer
- User sends to `/chat/generate` → always runs Retriever → Generator
- User sends to `/chat/pytest` → always runs Retriever → TestGenerator

**Problem**: The PS says "Agents must not run in a fixed sequence". We need a **router agent** that decides.

### What To Build

#### New File: `backend/app/services/agent_router.py`

```python
"""
Dynamic Multi-Agent Router.
Analyzes user query and decides which agents to invoke.
"""
import json
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel
from app.utils.llm import llm
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AgentAction(str, Enum):
    EXPLAIN = "EXPLAIN"        # Q&A → Retriever + Answerer
    GENERATE = "GENERATE"      # Code Gen → Retriever + Generator
    TEST = "TEST"              # PyTest → Retriever + TestGenerator
    DECOMPOSE = "DECOMPOSE"    # Complex → Planner + multiple sub-flows
    REFUSE = "REFUSE"          # Insufficient info → Safe refusal


class RoutingDecision(BaseModel):
    primary_action: AgentAction
    secondary_actions: List[AgentAction] = []
    reasoning: str
    confidence: float  # 0.0-1.0
    should_decompose: bool = False
    parallel_agents: List[AgentAction] = []  # agents that can run in parallel
    skip_agents: List[str] = []  # agents explicitly skipped


class AgentRouter:
    ROUTING_PROMPT = """You are a routing controller for RepoPilot.
Analyze the user query and decide which agents should handle it.

Available agents:
- EXPLAIN: Answer questions about the codebase (Q&A)
- GENERATE: Generate new code or modify existing code
- TEST: Generate PyTest test cases
- DECOMPOSE: Break complex queries into sub-questions first
- REFUSE: When the query is outside scope or unsafe

Rules:
- Simple questions → EXPLAIN only (skip DECOMPOSE, skip GENERATE)
- "Add X" / "Create X" / "Implement X" → GENERATE (may add TEST in parallel)
- "Write tests for X" → TEST only
- Complex multi-part questions → DECOMPOSE first, then EXPLAIN
- "Refactor X and add tests" → GENERATE + TEST in parallel
- Unsafe/irrelevant queries → REFUSE

Return JSON:
{
  "primary_action": "EXPLAIN|GENERATE|TEST|DECOMPOSE|REFUSE",
  "secondary_actions": ["TEST"],  
  "reasoning": "Why this routing",
  "confidence": 0.85,
  "should_decompose": false,
  "parallel_agents": ["TEST"],
  "skip_agents": ["DECOMPOSE"]
}"""

    async def route(self, query: str, repo_context: str = "") -> RoutingDecision:
        """Decide which agents to invoke for this query."""
        messages = [
            {"role": "system", "content": self.ROUTING_PROMPT},
            {"role": "user", "content": f"Query: {query}\nRepo context: {repo_context or 'General'}"}
        ]
        
        try:
            response = await llm.chat_completion(messages, json_mode=True)
            data = json.loads(response)
            return RoutingDecision(**data)
        except Exception as e:
            logger.error("routing_failed", error=str(e))
            # Fallback: heuristic routing
            return self._heuristic_route(query)
    
    def _heuristic_route(self, query: str) -> RoutingDecision:
        """Fast fallback if LLM routing fails."""
        q = query.lower()
        
        gen_keywords = ["add", "create", "implement", "build", "write code", "generate", "refactor", "modify"]
        test_keywords = ["test", "pytest", "unittest", "write tests"]
        refuse_keywords = ["delete prod", "drop database", "rm -rf"]
        
        if any(k in q for k in refuse_keywords):
            return RoutingDecision(primary_action=AgentAction.REFUSE, reasoning="Unsafe operation detected", confidence=0.95)
        
        if any(k in q for k in test_keywords):
            return RoutingDecision(primary_action=AgentAction.TEST, reasoning="Test generation request", confidence=0.9)
        
        if any(k in q for k in gen_keywords):
            return RoutingDecision(
                primary_action=AgentAction.GENERATE,
                secondary_actions=[AgentAction.TEST],
                parallel_agents=[AgentAction.TEST],
                reasoning="Code generation with parallel test gen",
                confidence=0.85
            )
        
        if len(q.split()) > 20:
            return RoutingDecision(
                primary_action=AgentAction.DECOMPOSE,
                secondary_actions=[AgentAction.EXPLAIN],
                should_decompose=True,
                reasoning="Complex query needs decomposition",
                confidence=0.7
            )
        
        return RoutingDecision(primary_action=AgentAction.EXPLAIN, reasoning="Simple Q&A", confidence=0.8, skip_agents=["GENERATE", "TEST", "DECOMPOSE"])


agent_router = AgentRouter()
```

#### Modify: `routes/chat.py` — New unified endpoint

Add a new `/chat/smart` endpoint that uses the router:

```python
@router.post("/smart")
async def smart_chat(request: ChatRequest):
    """Dynamic multi-agent routing endpoint."""
    from app.services.agent_router import agent_router, AgentAction
    
    # Step 1: Route
    decision = await agent_router.route(request.question)
    
    # Step 2: Execute based on routing
    result = {"routing": decision.model_dump()}
    
    if decision.primary_action == AgentAction.REFUSE:
        result["answer"] = "I cannot safely process this request."
        result["confidence"] = "low"
        return result
    
    # Parallel execution where possible
    tasks = {}
    if decision.primary_action == AgentAction.EXPLAIN or AgentAction.EXPLAIN in decision.secondary_actions:
        tasks["explain"] = _run_explain(request)
    if decision.primary_action == AgentAction.GENERATE or AgentAction.GENERATE in decision.secondary_actions:
        tasks["generate"] = _run_generate(request)
    if AgentAction.TEST in decision.parallel_agents:
        tasks["test"] = _run_test(request)
    
    # Run all tasks concurrently
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    
    # Merge results
    for key, res in zip(tasks.keys(), results):
        if not isinstance(res, Exception):
            result[key] = res
    
    return result
```

#### Modify: `models/chat.py` — Add routing fields to response

```python
class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
    confidence: AnswerConfidence = AnswerConfidence.MEDIUM
    assumptions: List[str] = []
    subquestions: Optional[List[str]] = None
    # NEW Round 2 fields:
    routing_decision: Optional[str] = None
    routing_reasoning: Optional[str] = None
    agents_used: List[str] = []
    agents_skipped: List[str] = []
```

---

## 📋 Feature 2: Iterative PyTest-Driven Refinement

**Owner: Member 2**
**Time: 6-7 hours**
**Concept**: Generate code → Generate tests → Run tests → If fail → Use failure as feedback → Refine code → Repeat (max 3-5 iterations)

### What Exists Today
- `test_generator.py` generates test code as a string
- `chatPanel.ts` `_handleRunTests()` creates a temp file and runs `pytest` in a terminal
- But there's **NO loop**, **NO feedback**, **NO auto-refinement**

### What To Build

#### New File: `backend/app/services/refinement_loop.py`

```python
"""
Iterative PyTest-Driven Refinement Loop.
Generates code → tests → runs → refines based on failures.
"""
import asyncio
import json
import subprocess
import tempfile
import os
from typing import Optional, List
from pydantic import BaseModel, Field
from app.utils.llm import llm
from app.utils.logger import get_logger
from app.services.generator import generator, GenerationResponse
from app.services.test_generator import test_generator
from app.services.retriever import retriever

logger = get_logger(__name__)
MAX_ITERATIONS = 4


class IterationResult(BaseModel):
    iteration: int
    code_generated: str
    tests_generated: str
    test_output: str
    tests_passed: bool
    failures: List[str] = []
    refinement_action: str = ""


class RefinementResult(BaseModel):
    success: bool
    total_iterations: int
    final_code: str
    final_tests: str
    iteration_log: List[IterationResult]
    final_test_output: str


class RefinementLoop:
    
    REFINE_PROMPT = """You are a code refinement agent.
The previous code generation produced code that FAILED tests.

TEST FAILURES:
{failures}

ORIGINAL CODE:
{code}

ORIGINAL TESTS:
{tests}

Analyze the failures and fix EITHER the code OR the tests (decide which is wrong).
Return JSON:
{{
  "fix_target": "code" or "tests",
  "reasoning": "Why this fix",
  "fixed_code": "the corrected code if fix_target is code",
  "fixed_tests": "the corrected tests if fix_target is tests"
}}"""

    async def run_refinement(
        self,
        repo_id: str,
        request: str,
        chat_history: Optional[List[dict]] = None,
    ) -> RefinementResult:
        """Run the full refinement loop."""
        iteration_log = []
        current_code = ""
        current_tests = ""
        
        for i in range(1, MAX_ITERATIONS + 1):
            logger.info("refinement_iteration", iteration=i, repo_id=repo_id)
            
            # Step 1: Generate code (first iteration) or use refined code
            if i == 1:
                gen_result = await generator.generate(repo_id, request, chat_history)
                # Extract the raw code from diffs
                current_code = self._extract_code_from_diffs(gen_result)
            
            # Step 2: Generate tests for the current code
            if i == 1 or not current_tests:
                test_result = await test_generator.generate_tests(
                    repo_id=repo_id,
                    custom_request=f"Generate tests for this code:\n```\n{current_code[:2000]}\n```"
                )
                current_tests = test_result.get("tests", "")
            
            # Step 3: Run tests
            test_output, passed, failures = await self._run_pytest(current_code, current_tests)
            
            iteration = IterationResult(
                iteration=i,
                code_generated=current_code[:500] + "..." if len(current_code) > 500 else current_code,
                tests_generated=current_tests[:500] + "..." if len(current_tests) > 500 else current_tests,
                test_output=test_output[:1000],
                tests_passed=passed,
                failures=failures,
            )
            
            if passed:
                iteration.refinement_action = "Tests passed — no refinement needed"
                iteration_log.append(iteration)
                break
            
            # Step 4: Refine
            refined = await self._refine(current_code, current_tests, test_output)
            if refined.get("fix_target") == "code":
                current_code = refined.get("fixed_code", current_code)
                iteration.refinement_action = f"Fixed CODE: {refined.get('reasoning', '')}"
            else:
                current_tests = refined.get("fixed_tests", current_tests)
                iteration.refinement_action = f"Fixed TESTS: {refined.get('reasoning', '')}"
            
            iteration_log.append(iteration)
        
        final_passed = iteration_log[-1].tests_passed if iteration_log else False
        
        return RefinementResult(
            success=final_passed,
            total_iterations=len(iteration_log),
            final_code=current_code,
            final_tests=current_tests,
            iteration_log=iteration_log,
            final_test_output=iteration_log[-1].test_output if iteration_log else "",
        )
    
    def _extract_code_from_diffs(self, gen_result: GenerationResponse) -> str:
        """Extract raw code from generation diffs."""
        parts = []
        for diff in gen_result.diffs:
            if diff.code:
                parts.append(f"# File: {diff.file_path}\n{diff.code}")
            elif diff.diff:
                parts.append(f"# File: {diff.file_path}\n{diff.diff}")
        return "\n\n".join(parts) if parts else gen_result.plan
    
    async def _run_pytest(self, code: str, tests: str) -> tuple:
        """Run pytest in a subprocess and return (output, passed, failures)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = os.path.join(tmpdir, "generated_code.py")
            test_file = os.path.join(tmpdir, "test_generated.py")
            
            with open(code_file, "w") as f:
                f.write(code)
            
            # Prepend an import of the generated code to the test file
            test_with_import = f"import sys\nsys.path.insert(0, r'{tmpdir}')\n{tests}"
            with open(test_file, "w") as f:
                f.write(test_with_import)
            
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", test_file, "-v", "--tb=short", "--no-header"],
                    capture_output=True, text=True, timeout=30, cwd=tmpdir
                )
                output = result.stdout + result.stderr
                passed = result.returncode == 0
                
                # Extract failure lines
                failures = []
                for line in output.split("\n"):
                    if "FAILED" in line or "ERROR" in line or "AssertionError" in line.replace("AssertionError", "AssertionError"):
                        failures.append(line.strip())
                
                return output, passed, failures
            except subprocess.TimeoutExpired:
                return "Test execution timed out (30s limit)", False, ["Timeout"]
            except FileNotFoundError:
                return "pytest not found — install with: pip install pytest", False, ["pytest not installed"]
            except Exception as e:
                return f"Error running tests: {str(e)}", False, [str(e)]
    
    async def _refine(self, code: str, tests: str, failure_output: str) -> dict:
        """Use LLM to analyze failures and fix code or tests."""
        prompt = self.REFINE_PROMPT.format(
            failures=failure_output[:2000],
            code=code[:3000],
            tests=tests[:2000]
        )
        
        messages = [
            {"role": "system", "content": "You are a debugging expert. Fix the failing code or tests."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await llm.chat_completion(messages, json_mode=True)
            return json.loads(response)
        except Exception as e:
            logger.error("refinement_failed", error=str(e))
            return {"fix_target": "tests", "reasoning": f"LLM refinement failed: {e}", "fixed_tests": tests}


refinement_loop = RefinementLoop()
```

#### Modify: `routes/chat.py` — Add `/chat/refine` endpoint

```python
@router.post("/refine")
async def refine_code(request: CodeGenerationRequest):
    """Iterative PyTest-driven refinement loop."""
    from app.services.refinement_loop import refinement_loop
    result = await refinement_loop.run_refinement(
        request.repo_id, request.request, request.chat_history
    )
    return result.model_dump()
```

---

## 📋 Feature 3: LLM vs LLM Evaluation Layer

**Owner: Member 3**
**Time: 4-5 hours**
**Concept**: After code gen, TWO different LLMs independently review the code. A controller merges/picks the best.

### What To Build

#### New File: `backend/app/services/evaluator.py`

```python
"""
LLM vs LLM Evaluation Layer.
Two independent LLM agents review generated code.
A controller decides which improvements to accept.
"""
import json
import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from app.utils.llm import llm
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AgentReview(BaseModel):
    agent_name: str
    score: float  # 0-10
    issues: list[str] = []
    suggestions: list[str] = []
    verdict: str  # APPROVE / NEEDS_CHANGES / REJECT


class EvaluationResult(BaseModel):
    agent_a_review: AgentReview
    agent_b_review: AgentReview
    controller_decision: str  # ACCEPT_A / ACCEPT_B / MERGE / REJECT_BOTH
    controller_reasoning: str
    final_code: str
    merged_improvements: list[str] = []


class Evaluator:
    
    REVIEW_PROMPT = """You are Code Reviewer {agent_name}.
Review this generated code for:
1. Correctness — Will it work? Any bugs?
2. Edge Cases — What inputs could break it?
3. Repository Alignment — Does it follow the patterns from the repo context?
4. Security — Any vulnerabilities?

REPOSITORY CONTEXT:
{repo_context}

GENERATED CODE:
{code}

Return JSON:
{{
  "score": 7.5,
  "issues": ["Issue 1", "Issue 2"],
  "suggestions": ["Fix X", "Add Y"],
  "verdict": "APPROVE|NEEDS_CHANGES|REJECT",
  "improved_code": "If NEEDS_CHANGES, provide the improved version here"
}}"""

    CONTROLLER_PROMPT = """You are the Code Quality Controller.
Two independent reviewers have evaluated the generated code.

AGENT A (Groq/Llama) Review:
Score: {a_score}/10
Issues: {a_issues}
Suggestions: {a_suggestions}

AGENT B (Gemini) Review:
Score: {b_score}/10
Issues: {b_issues}
Suggestions: {b_suggestions}

ORIGINAL CODE:
{original_code}

AGENT A's IMPROVED CODE (if any):
{a_improved}

AGENT B's IMPROVED CODE (if any):
{b_improved}

Decide:
- If both approve with high scores → ACCEPT original
- If one has good improvements → ACCEPT that agent's version
- If both have improvements → MERGE the best of both
- If both reject → REJECT

Return JSON:
{{
  "decision": "ACCEPT_A|ACCEPT_B|MERGE|ACCEPT_ORIGINAL|REJECT",
  "reasoning": "Why",
  "final_code": "The final accepted/merged code",
  "merged_improvements": ["What was improved"]
}}"""

    async def evaluate(self, code: str, repo_context: str = "") -> EvaluationResult:
        """Run dual-LLM evaluation."""
        
        # Run both reviews IN PARALLEL (different models)
        review_a_task = self._review_with_groq(code, repo_context)
        review_b_task = self._review_with_gemini(code, repo_context)
        
        review_a_raw, review_b_raw = await asyncio.gather(
            review_a_task, review_b_task, return_exceptions=True
        )
        
        # Parse reviews
        agent_a = self._parse_review("Agent-A (Groq/Llama)", review_a_raw)
        agent_b = self._parse_review("Agent-B (Gemini)", review_b_raw)
        
        # Controller decides
        controller_result = await self._controller_decide(code, agent_a, agent_b, 
                                                           review_a_raw, review_b_raw)
        
        return EvaluationResult(
            agent_a_review=agent_a,
            agent_b_review=agent_b,
            controller_decision=controller_result.get("decision", "ACCEPT_ORIGINAL"),
            controller_reasoning=controller_result.get("reasoning", ""),
            final_code=controller_result.get("final_code", code),
            merged_improvements=controller_result.get("merged_improvements", []),
        )
    
    async def _review_with_groq(self, code: str, repo_context: str) -> dict:
        """Review using Groq (primary LLM)."""
        prompt = self.REVIEW_PROMPT.format(agent_name="A (Groq)", repo_context=repo_context[:2000], code=code[:3000])
        messages = [{"role": "system", "content": "You are a strict code reviewer."}, {"role": "user", "content": prompt}]
        try:
            response = await llm.chat_completion(messages, json_mode=True)
            return json.loads(response)
        except Exception as e:
            return {"score": 5, "issues": [f"Review failed: {e}"], "suggestions": [], "verdict": "APPROVE"}
    
    async def _review_with_gemini(self, code: str, repo_context: str) -> dict:
        """Review using Gemini (second LLM — different model family)."""
        import google.generativeai as genai
        from app.config import settings
        
        if not settings.gemini_api_key:
            return {"score": 5, "issues": ["Gemini not configured"], "suggestions": [], "verdict": "APPROVE"}
        
        prompt = self.REVIEW_PROMPT.format(agent_name="B (Gemini)", repo_context=repo_context[:2000], code=code[:3000])
        
        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(prompt)
            text = response.text.strip()
            # Clean markdown blocks
            if text.startswith("```"):
                import re
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
            return json.loads(text)
        except Exception as e:
            return {"score": 5, "issues": [f"Gemini review failed: {e}"], "suggestions": [], "verdict": "APPROVE"}
    
    def _parse_review(self, agent_name: str, raw: dict | Exception) -> AgentReview:
        if isinstance(raw, Exception):
            return AgentReview(agent_name=agent_name, score=5, verdict="APPROVE", issues=[str(raw)])
        return AgentReview(
            agent_name=agent_name,
            score=raw.get("score", 5),
            issues=raw.get("issues", []),
            suggestions=raw.get("suggestions", []),
            verdict=raw.get("verdict", "APPROVE"),
        )
    
    async def _controller_decide(self, original_code, agent_a, agent_b, raw_a, raw_b) -> dict:
        prompt = self.CONTROLLER_PROMPT.format(
            a_score=agent_a.score, a_issues=agent_a.issues, a_suggestions=agent_a.suggestions,
            b_score=agent_b.score, b_issues=agent_b.issues, b_suggestions=agent_b.suggestions,
            original_code=original_code[:2000],
            a_improved=raw_a.get("improved_code", "None") if isinstance(raw_a, dict) else "None",
            b_improved=raw_b.get("improved_code", "None") if isinstance(raw_b, dict) else "None",
        )
        messages = [{"role": "system", "content": "You are a senior engineering lead making final decisions."}, {"role": "user", "content": prompt}]
        try:
            response = await llm.chat_completion(messages, json_mode=True)
            return json.loads(response)
        except Exception as e:
            return {"decision": "ACCEPT_ORIGINAL", "reasoning": f"Controller failed: {e}", "final_code": original_code}


evaluator = Evaluator()
```

---

## 📋 Feature 4: Risk and Change Impact Analysis

**Owner: Member 3 (after Feature 3)**
**Time: 3-4 hours**

#### New File: `backend/app/services/impact_analyzer.py`

```python
"""
Risk and Change Impact Analyzer.
Reports files changed, files indirectly affected, and risks.
"""
import json
import re
from typing import List
from pydantic import BaseModel, Field
from app.utils.llm import llm
from app.utils.logger import get_logger
from app.services.retriever import retriever
from app.services.repo_manager import repo_manager

logger = get_logger(__name__)


class ImpactReport(BaseModel):
    files_directly_changed: List[str]
    files_indirectly_affected: List[str] = []
    risks: List[str] = []
    severity: str = "LOW"  # LOW / MEDIUM / HIGH / CRITICAL
    reasoning: str = ""
    recommendations: List[str] = []


class ImpactAnalyzer:
    
    IMPACT_PROMPT = """You are a change impact analysis agent.
Given the code changes and the repository context, analyze:

1. FILES DIRECTLY CHANGED: Which files are being modified?
2. FILES INDIRECTLY AFFECTED: Which other files import/depend on the changed files?
3. RISKS: What could break? What side effects exist?
4. SEVERITY: LOW (cosmetic) / MEDIUM (logic change) / HIGH (API change) / CRITICAL (data loss risk)

REPOSITORY FILE LIST:
{file_list}

IMPORT RELATIONSHIPS FOUND:
{imports}

CODE CHANGES:
{changes}

Return JSON:
{{
  "files_directly_changed": ["file1.py"],
  "files_indirectly_affected": ["file2.py that imports file1"],
  "risks": ["Risk 1", "Risk 2"],
  "severity": "MEDIUM",
  "reasoning": "Why these risks exist",
  "recommendations": ["Test X", "Review Y"]
}}"""

    async def analyze(self, repo_id: str, changes: str, changed_files: List[str]) -> ImpactReport:
        """Analyze impact of code changes."""
        
        # Get file list
        try:
            files = await repo_manager.list_files(repo_id)
            file_list = "\n".join(f["file_path"] for f in files[:100])
        except Exception:
            file_list = "File list unavailable"
        
        # Find imports of changed files
        imports = await self._find_importers(repo_id, changed_files)
        
        prompt = self.IMPACT_PROMPT.format(
            file_list=file_list[:3000],
            imports=imports[:2000],
            changes=changes[:3000]
        )
        
        messages = [
            {"role": "system", "content": "You are a senior engineer analyzing change impact."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await llm.chat_completion(messages, json_mode=True)
            data = json.loads(response)
            return ImpactReport(**data)
        except Exception as e:
            logger.error("impact_analysis_failed", error=str(e))
            return ImpactReport(
                files_directly_changed=changed_files,
                risks=[f"Impact analysis failed: {e}"],
                severity="MEDIUM",
                reasoning="Automated analysis unavailable"
            )
    
    async def _find_importers(self, repo_id: str, changed_files: List[str]) -> str:
        """Find files that import the changed files using retriever."""
        import_info = []
        for file_path in changed_files[:5]:
            module_name = file_path.replace("/", ".").replace(".py", "")
            base_name = file_path.split("/")[-1].replace(".py", "")
            
            try:
                chunks = await retriever.retrieve(
                    repo_id, f"import {base_name} from {module_name}", k=5
                )
                for chunk in chunks:
                    if any(kw in chunk.content.lower() for kw in [f"import {base_name}", f"from {module_name}", f"from .{base_name}"]):
                        import_info.append(f"{chunk.metadata.file_path} imports {file_path}")
            except Exception:
                continue
        
        return "\n".join(import_info) if import_info else "No import relationships found"


impact_analyzer = ImpactAnalyzer()
```

#### New Endpoint in `routes/chat.py`:

```python
@router.post("/impact")
async def analyze_impact(request: dict):
    """Analyze risk and impact of code changes."""
    from app.services.impact_analyzer import impact_analyzer
    result = await impact_analyzer.analyze(
        repo_id=request["repo_id"],
        changes=request.get("changes", ""),
        changed_files=request.get("changed_files", [])
    )
    return result.model_dump()
```

---

## 📋 Feature 4 (Frontend): UI Updates for All Features

**Owner: Member 4**
**Time: 6-8 hours (parallel with backend)**

### What to show in the UI for each feature:

1. **Routing Decision Panel** — Show "🧠 Router decided: EXPLAIN (skipped: GENERATE, TEST)"
2. **Refinement Loop Timeline** — Show iterations: "Iteration 1: ❌ 3 tests failed → Iteration 2: ❌ 1 test failed → Iteration 3: ✅ All passed"
3. **LLM vs LLM Review** — Show side-by-side: "Agent A (Groq): 8/10 | Agent B (Gemini): 7/10 | Decision: MERGE"
4. **Impact Report** — Show "⚠️ 2 files directly changed, 5 files indirectly affected, Risk: MEDIUM"

### Minimal changes needed in `page.tsx`:

Add new message types and render them. Focus on adding collapsible sections to the `MessageContent` component that show routing, evaluation, refinement, and impact data.

---

## ⏰ Detailed Timeline (24 Hours)

| Time Block | Member 1 | Member 2 | Member 3 | Member 4 |
|---|---|---|---|---|
| **Hour 0-1** | Git setup, create branches | Git setup, create branches | Git setup, create branches | Git setup, create branches |
| **Hour 1-3** | Build `agent_router.py` | Build `refinement_loop.py` | Build `evaluator.py` | Add routing UI component |
| **Hour 3-5** | Wire router into `chat.py` | Wire refinement into `chat.py` | Build `impact_analyzer.py` | Add refinement timeline UI |
| **Hour 5-7** | Test routing with different queries | Test the loop with real code gen | Wire evaluator + impact into `chat.py` | Add LLM-vs-LLM review UI |
| **Hour 7-8** | **Merge Member 1 branch** | Debug subprocess pytest runner | Test evaluator with Groq + Gemini | Add impact report UI |
| **Hour 8-10** | Help Member 2 debug | **Merge Member 2 branch** | **Merge Member 3 branch** | **Merge Member 4 branch** |
| **Hour 10-12** | Integration testing all endpoints | Integration testing all endpoints | Integration testing all endpoints | Polish UI, fix bugs |
| **Hour 12-14** | Fix bugs from integration | Fix bugs from integration | Fix bugs from integration | Fix frontend bugs |
| **Hour 14-16** | Update `EXPLAIN.md` + docs | Update demo script | Record demo video | Final UI polish |
| **Hour 16-18** | Full end-to-end demo rehearsal | Full end-to-end demo rehearsal | Full end-to-end demo rehearsal | Full end-to-end demo rehearsal |
| **Hour 18-20** | Sleep | Sleep | Sleep | Sleep |
| **Hour 20-22** | Final fixes + submission prep | Final fixes | Final fixes | Final fixes |
| **Hour 22-24** | **SUBMIT** | **SUBMIT** | **SUBMIT** | **SUBMIT** |

---

## 🔀 Git Workflow Instructions (Send This to Team)

### For ALL Members — DO THIS FIRST:

```bash
# 1. Pull latest main
git checkout main
git pull origin main

# 2. Create your feature branch
git checkout -b feature/round2/<your-feature>

# Examples:
# Member 1: git checkout -b feature/round2/agent-router
# Member 2: git checkout -b feature/round2/refinement-loop
# Member 3: git checkout -b feature/round2/evaluator-impact
# Member 4: git checkout -b feature/round2/frontend-r2
```

### While Working:

```bash
# Commit frequently (every 30-60 mins)
git add .
git commit -m "feat(round2): <what you did>"

# Push your branch
git push origin feature/round2/<your-feature>
```

### Before Merging:

```bash
# Rebase onto latest main first
git checkout main
git pull origin main
git checkout feature/round2/<your-feature>
git rebase main

# If conflicts: fix them, then:
git add .
git rebase --continue

# Push (force because of rebase)
git push origin feature/round2/<your-feature> --force-with-lease
```

### Merge Order (IMPORTANT — follow this sequence):

1. **Member 1** merges first (router — no dependencies)
2. **Member 3** merges second (evaluator + impact — no dependencies)
3. **Member 2** merges third (refinement — may use evaluator)
4. **Member 4** merges last (frontend — depends on all backend APIs)

### After Each Merge:

```bash
# Everyone else rebases
git checkout feature/round2/<your-feature>
git pull --rebase origin main
```

---

## 🧪 Testing Each Feature

### Feature 1 (Router):
```bash
curl -X POST http://localhost:8000/chat/smart \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "YOUR_REPO_ID", "question": "Add a health check endpoint"}'

# Expected: routing_decision should be "GENERATE", not "EXPLAIN"
```

### Feature 2 (Refinement):
```bash
curl -X POST http://localhost:8000/chat/refine \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "YOUR_REPO_ID", "request": "Add input validation to the login function"}'

# Expected: iteration_log with 1-4 entries, final tests_passed ideally true
```

### Feature 3 (LLM vs LLM):
```bash
# This is called internally by the /chat/smart endpoint when routing to GENERATE
# Check logs for "Agent-A" and "Agent-B" reviews
```

### Feature 4 (Impact):
```bash
curl -X POST http://localhost:8000/chat/impact \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "YOUR_REPO_ID", "changes": "Added logging to auth.py", "changed_files": ["auth.py"]}'

# Expected: files_indirectly_affected should include files that import auth.py
```

---

## 🔴 Critical Reminders

1. **DO NOT break existing endpoints** — `/ask`, `/generate`, `/pytest` must keep working
2. **The refinement loop runs pytest as a subprocess** — make sure `pytest` is installed in the backend env: `pip install pytest`
3. **Gemini calls in evaluator.py use the synchronous SDK** — wrap in `asyncio.to_thread()` if needed
4. **Keep LLM calls under 30 seconds** — add timeouts everywhere
5. **Member 4**: The frontend doesn't need to show EVERYTHING. Show routing + iteration count + impact summary. Don't over-engineer the UI.
