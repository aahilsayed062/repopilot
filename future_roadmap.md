# RepoPilot — Future Roadmap & Setup Guide
> **Last Updated:** 2026-02-16 | **Branch:** `main`

> [!IMPORTANT]
> **Prerequisites: Install Ollama & Pull Models**
> Before running RepoPilot, you must run these commands in your terminal:
> ```bash
> ollama pull qwen2.5-coder:3b
> ollama pull qwen2.5-coder:1.5b
> ```

---

## 📊 Current Feature Status

| # | Feature | Status | Key Files |
|---|---------|--------|-----------|
| 1 | Dynamic Multi-Agent Routing | ✅ **DONE** | `agent_router.py`, `chat.py /smart` |
| 2 | Iterative PyTest-Driven Refinement | ✅ **DONE** | `refinement_loop.py`, `chat.py /refine` |
| 3 | LLM vs LLM Evaluation Layer | 🔴 **TODO** | `evaluator.py` (create) |
| 4 | Risk & Change Impact Analysis | 🔴 **TODO** | `impact_analyzer.py` (create) |

---

## 🔧 Ollama Setup & Performance Guide

### Installation
```bash
# 1. Download Ollama from https://ollama.com/download
# 2. Install it (Windows installer or WSL)

# 3. Pull the models we use
ollama pull qwen2.5-coder:3b     # Agent A — primary (balanced speed/smarts)
ollama pull qwen2.5-coder:1.5b   # Agent B — reviewer (fast, lightweight)

# 4. Verify
ollama list   # Should show both models
```

### How Ollama Works With RepoPilot
```
User Query → Extension → Backend → LLM Service (llm.py)
                                        │
                                  ┌─────▼─────┐
                                  │  Ollama    │  ← Runs on localhost:11434
                                  │  (local)   │  ← No internet needed
                                  │            │  ← No token limits
                                  └────────────┘
```

- **LLM calls** (chat, code gen, routing) → **Ollama** (local, unlimited)
- **Embeddings** (vector search) → **Gemini** (free API, no token concern)
- Groq/OpenAI are **disabled** in `.env` but can be re-enabled as fallback

### Performance & Speed

**Will it be slow?** It depends on your hardware:

| Model | RAM Needed | Speed (tokens/sec) | Good For |
|-------|-----------|-------------------|----------|
| `qwen2.5-coder:1.5b` | ~2 GB | 30-80 tok/s | Fast routing, quick reviews |
| `qwen2.5-coder:3b` | ~2.5 GB | 20-50 tok/s | Balanced, good coding |

**Tips to make Ollama faster:**

1. **Use the 1.5b model for routing** — The agent router uses LLM to decide which agent to run. This should be fast, not smart. Configure it to use Model B:
   ```python
   # In agent_router.py, the route() method already uses llm.chat_completion()
   # You can add provider_override="ollama_b" for faster routing
   response = await llm.chat_completion(messages, json_mode=True, provider_override="ollama_b")
   ```

2. **Reduce context length** — Ollama defaults to 2048 tokens context. For longer answers:
   ```python
   # In llm.py _call_ollama, the num_ctx option controls context window
   "options": {
       "temperature": temperature,
       "num_ctx": 4096,  # Increase for longer code contexts
   }
   ```

3. **Keep models warm** — By default Ollama unloads models after 5 mins. Keep them in RAM:
   ```bash
   # Set keep_alive to infinite
   curl http://localhost:11434/api/generate -d '{"model": "qwen2.5-coder:3b", "keep_alive": -1}'
   ```

4. **GPU acceleration** — If you have an NVIDIA GPU, Ollama uses it automatically. Check with:
   ```bash
   ollama ps  # Shows which models are loaded and GPU usage
   ```

5. **If too slow, swap to 1.5b for everything** — Edit `.env`:
   ```
   OLLAMA_MODEL_A=qwen2.5-coder:1.5b
   OLLAMA_MODEL_B=qwen2.5-coder:1.5b
   ```

### Troubleshooting
- **"Connection refused"** → Ollama isn't running. Start it: `ollama serve`
- **Very slow first response** → Model is loading into RAM. Subsequent calls are faster
- **Out of memory** → Use smaller model: `ollama pull qwen2.5-coder:1.5b`
- **Backend shows "mock" provider** → Ollama check failed at startup. Restart backend after starting Ollama

---

## 🛣️ Feature 2: Iterative PyTest Refinement (✅ Done)

**What it does:** Generate code → Generate tests → Run pytest → If fails, refine → Repeat (max 4 iterations)

**How it works:**
1. `/chat/refine` endpoint receives the code request
2. `refinement_loop.py` orchestrates:
   - Step 1: Generate code via `generator.py`
   - Step 2: Generate tests via `test_generator.py`
   - Step 3: Run pytest in a sandboxed temp directory
   - Step 4: If tests fail, ask LLM to fix code/tests using failure output
   - Step 5: Repeat until tests pass or max iterations reached

**Already done:** Full implementation in `refinement_loop.py` and `/refine` endpoint.

---

## 🛣️ Feature 3: LLM vs LLM Evaluation Layer (🔴 Next)

**What it does:** After code generation, two LLM agents independently review the code. A controller decides which version to accept or how to merge improvements.

### Implementation Plan

**Step 1: Create `backend/app/services/evaluator.py`**
```python
class CodeEvaluator:
    """Two-model code review system."""
    
    REVIEW_PROMPT = """Review this generated code:
    - Correctness: Does it do what was asked?
    - Edge cases: Are there unhandled edge cases?
    - Repo alignment: Does it match the codebase style?
    
    Score each 1-10 and explain issues."""
    
    async def evaluate(self, code: str, context: str) -> dict:
        # Run both models in parallel
        review_a, review_b = await asyncio.gather(
           # `_review_with_model_a(code)` → Uses `provider_override="ollama"` (Model A: qwen2.5-coder:3b)
            llm.chat_completion(messages, provider_override="ollama_b"), # Model B (1.5b)
        )
        # Controller merges feedback
        return self._merge_reviews(review_a, review_b)
```

**Step 2: Add `/chat/evaluate` endpoint**
```python
@router.post("/evaluate")
async def evaluate_code(request):
    result = await evaluator.evaluate(code, context)
    return result
```

**Step 3: Wire into `/smart` routing** — After GENERATE, before TEST, run evaluation

**Estimated effort:** ~2-3 hours

---

## 🛣️ Feature 4: Risk & Change Impact Analysis (🔴 After Feature 3)

**What it does:** After code changes are finalized, the system reports which files are directly changed, which are indirectly affected, and what risks are introduced.

### Implementation Plan

**Step 1: Create `backend/app/services/impact_analyzer.py`**
```python
class ImpactAnalyzer:
    """Analyzes change impact using RAG retrieval."""
    
    async def analyze(self, changed_files: list, repo_id: str) -> dict:
        # 1. For each changed file, find files that import it
        # 2. Use retriever to find related code chunks
        # 3. Ask LLM to assess risk level
        # 4. Return structured report
        return {
            "directly_changed": [...],
            "indirectly_affected": [...],
            "risk_level": "MEDIUM",
            "risks": ["Breaking change in public API", ...],
            "recommendations": [...]
        }
```

**Step 2: Add `/chat/impact` endpoint**

**Step 3: Show impact report in extension after code generation**

**Estimated effort:** ~2-3 hours

---

## 🚀 Quick Start: Resume Development

```bash
# 1. Ensure Ollama is running with both models
ollama serve
ollama pull qwen2.5-coder:3b
ollama pull qwen2.5-coder:1.5b

# 2. Start backend
cd backend
.\venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000

# 3. Open VS Code Extension
# Press F5 in the repopilot directory to launch extension dev host

# 4. Next task: Create evaluator.py (Feature 3)
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `backend/app/utils/llm.py` | LLM service — Ollama (primary), Gemini/OpenAI (fallback) |
| `backend/app/config.py` | Config — Ollama URLs, model names, settings |
| `backend/app/services/agent_router.py` | Feature 1: Dynamic query routing |
| `backend/app/services/refinement_loop.py` | Feature 2: PyTest refinement loop |
| `backend/app/routes/chat.py` | All endpoints: /smart, /ask, /generate, /pytest, /refine |
| `backend/app/services/answerer.py` | Grounded Q&A with citations |
| `backend/app/services/test_generator.py` | PyTest generation with 6-strategy parser |
| `.env` | Ollama config, Gemini key (embeddings only) |
