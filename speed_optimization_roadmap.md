# RepoPilot — Speed Optimization Roadmap

> **Goal:** Reduce perceived and actual latency to approach "near-instant" feel (like GitHub Copilot / Antigravity), while maintaining answer quality.

---

## Current Bottleneck Analysis

| Bottleneck | Where | Typical Time | % of Total |
|-----------|-------|-------------|-----------|
| **Ollama cold start** | First call after idle loads model into VRAM | 5–30s | Dominant on first query |
| **Ollama inference** | qwen2.5-coder:3b (3B params, ~2B quantized) | 8–20s per call | ~40-50% of steady-state |
| **Multiple LLM calls per request** | /smart = route + explain/generate + evaluate (critic+defender+controller) = 4-6 calls | 40–90s total | Core problem |
| **Embedding (indexing)** | nomic-embed-text via Ollama API, 50 texts/batch | 15–55s for medium repo | One-time |
| **Retriever** | ChromaDB query + reranking | 0.5–2s | Negligible |
| **Network overhead** | httpx ↔ Ollama (localhost), extension ↔ backend | <100ms | Negligible |

### Why Copilot/Antigravity Are Fast

1. **Cloud inference** — NVIDIA A100/H100 clusters serving models with <500ms latency.
2. **Smaller specialized models** — Purpose-trained for code completion (not general chat).
3. **Speculative decoding** — Draft model generates candidates, large model verifies in parallel.
4. **Aggressive caching** — Common patterns pre-computed; semantic cache for repeated queries.
5. **Edge optimization** — Models compiled with TensorRT/ONNX for specific hardware.

We are running locally on consumer hardware without those advantages. Below are options ranked by **effort vs. impact**.

---

## Option 1: Model Warm-Keeping (Ollama `keep_alive`)

**Impact: HIGH | Effort: LOW | Risk: LOW**

Ollama unloads models after 5 minutes of inactivity. The next call pays 5–30s cold start.

### What to Do
- Set `keep_alive` parameter in every Ollama API call:
  ```json
  { "model": "qwen2.5-coder:3b", "keep_alive": "24h" }
  ```
- Or configure Ollama globally: `OLLAMA_KEEP_ALIVE=24h`
- Add a **heartbeat** — a lightweight `/api/generate` call every 4 minutes to keep the model loaded.
- Pre-warm both models on backend startup.

### Expected Gain
- Eliminates 5–30s cold-start penalty on first query and after idle periods.
- **Time saved: 5–30s on first call, 0s on subsequent calls.**

---

## Option 2: Parallel LLM Calls (Already Partially Done)

**Impact: HIGH | Effort: MEDIUM | Risk: LOW**

Currently `/smart` runs:
- Phase A: EXPLAIN + GENERATE in parallel ✅ (done)
- Phase B: EVALUATE (critic + defender + controller) — currently **sequential** in evaluator.py
- Phase C: TEST

### What to Do
- **Critic and Defender already run in parallel** (asyncio.gather) ✅ — verify this is working.
- **Pipeline overlap:** Start evaluation as soon as diffs are available, while streaming the explain answer to the user. Return early with "evaluation pending" and update when done.
- **Speculative test generation:** Start test generation optimistically while evaluation runs. If evaluation says REQUEST_REVISION, discard test results.

### Expected Gain
- Saves 8–15s by overlapping evaluation and test generation.

---

## Option 3: Smaller/Faster Models

**Impact: VERY HIGH | Effort: LOW | Risk: MEDIUM (quality tradeoff)**

Current: `qwen2.5-coder:3b` (Agent A) + `qwen2.5-coder:1.5b` (Agent B/routing).

### Options to Evaluate

| Model | Params | Speed (tok/s on CPU) | Quality | Use Case |
|-------|--------|---------------------|---------|----------|
| `qwen2.5-coder:0.5b` | 0.5B | ~80-120 tok/s | Basic | Routing, simple explains |
| `qwen2.5-coder:1.5b` | 1.5B | ~40-70 tok/s | Good | Current Agent B |
| `qwen2.5-coder:3b` | 3B | ~20-40 tok/s | Very Good | Current Agent A |
| `qwen2.5-coder:7b` | 7B | ~10-20 tok/s | Excellent | Too slow for local |
| `deepseek-coder-v2:lite` | 2.4B | ~30-50 tok/s | Comparable to 3B | Worth testing |
| `starcoder2:3b` | 3B | ~20-40 tok/s | Code-focused | Alternative |

### Recommended Configuration
- **Router:** `qwen2.5-coder:0.5b` — routing is a simple classification, 0.5B is sufficient.
- **Explain/Answer:** `qwen2.5-coder:1.5b` — quality acceptable for Q&A.
- **Generate/Evaluate:** `qwen2.5-coder:3b` — keep quality where it matters most.

### What to Do
- Pull `qwen2.5-coder:0.5b` and benchmark routing accuracy vs. 1.5b.
- If routing accuracy holds (>90% agreement), switch router to 0.5b.
- Consider using 1.5b for the explain agent (not code-critical).

### Expected Gain
- Router: 0.5–1s instead of 2–4s (3-4x faster).
- Explain agent: 30-50% faster with 1.5b if currently using 3b for explains.

---

## Option 4: Reduce Token Count (Prompt Engineering)

**Impact: HIGH | Effort: MEDIUM | Risk: LOW**

LLM inference time scales linearly with input + output tokens. Current prompts may be over-verbose.

### What to Do

1. **System prompt compression:**
   - Current system prompts in answerer.py, generator.py, evaluator.py are 200-400 tokens each.
   - Compress to essential instructions only. Use bullet points, abbreviations.
   - Target: 50% reduction per prompt.

2. **Context window trimming:**
   - Currently retriever returns `top_k=3` chunks of up to 150 lines each.
   - Trim chunks to only the most relevant 30-50 lines.
   - Use a lightweight "chunk summary" instead of full chunk text for context.

3. **Reduce `max_tokens` per agent:**
   - Router: max_tokens=128 (currently 512) — only needs a JSON classification.
   - Evaluator critic/defender: max_tokens=256 — feedback is concise.
   - Controller: max_tokens=256.
   - Keep generator at 512+ (needs to output full code).

4. **Skip redundant context:**
   - Don't send full retriever context to both EXPLAIN and EVALUATE.
   - Evaluate only needs the generated diffs + original request.

### Expected Gain
- 20-40% faster per LLM call (fewer tokens to process).
- Multiplicative across 4-6 calls per /smart request.

---

## Option 5: Semantic Response Cache

**Impact: VERY HIGH (repeat queries) | Effort: MEDIUM | Risk: LOW**

### What to Do

1. **Exact-match cache:** Hash `(repo_id, question, commit_hash)` → cache response in memory/Redis.
   - TTL: 10 minutes or until re-index.
   - Instant response for repeated questions.

2. **Semantic cache:** Embed the question, find nearest cached question (cosine > 0.95).
   - Reuse cached response if the question is semantically identical.
   - Avoids redundant LLM calls for rephrased questions.

3. **Routing cache:** Cache `question_hash → routing_decision`.
   - Same question always routes the same way.
   - Saves one LLM call (the router).

4. **Embedding cache (already has hash-based dedup):**
   - Current: embeddings.py has content-hash dedup.
   - Persist embedding cache to disk between restarts.

### Expected Gain
- **Cached hit: <100ms response** (instant).
- First query: no change.
- Typical session: 30-50% of queries may hit cache (similar questions, re-asks).

---

## Option 6: Persistent Index (Skip Re-Indexing)

**Impact: HIGH (repeat sessions) | Effort: LOW | Risk: LOW**

Currently `USE_PERSISTENT_INDEX=False` — ChromaDB is ephemeral, re-indexes every restart.

### What to Do
- Set `USE_PERSISTENT_INDEX=True` in `.env`.
- ChromaDB persists to `data/<repo>/chroma/`.
- On restart, check if `commit_hash` matches — skip indexing entirely.
- Add incremental indexing: only re-embed files that changed since last index.

### Expected Gain
- **Eliminates 15–55s indexing time** on repeat sessions.
- Incremental mode: < 2s for typical code changes.

---

## Option 7: GPU Acceleration (Ollama)

**Impact: VERY HIGH | Effort: LOW (if GPU available) | Risk: NONE**

Ollama automatically uses GPU if available (CUDA/ROCm/Metal).

### What to Do
- Verify GPU is being used: `ollama ps` → check "Processors" column.
- If not using GPU: install CUDA drivers + Ollama with GPU support.
- Set `OLLAMA_NUM_GPU=999` to maximize GPU offloading.
- For low-VRAM GPUs (4-6GB): quantize models to Q4_K_M:
  ```bash
  ollama pull qwen2.5-coder:3b-instruct-q4_K_M
  ```

### Expected Gain on GPU
- 3B model: **60-120 tok/s** (vs. 20-40 on CPU) = **3x faster**.
- 1.5B model: **100-200 tok/s** = near-instant for short responses.
- Total /smart request: 15-30s instead of 40-90s.

---

## Option 8: Streaming Everywhere (Perceived Speed)

**Impact: HIGH (UX) | Effort: MEDIUM | Risk: LOW**

Users perceive streaming as faster even if total time is the same.

### What to Do
1. **Already done:** Explain-only queries now use streaming ✅.
2. **Smart endpoint streaming:** Return routing decision immediately, then stream explain answer, then append generation/evaluation as they complete.
   - Requires restructuring `/smart` to use SSE (Server-Sent Events).
   - Extension processes partial results and updates the webview incrementally.
3. **Progressive rendering:** Show plan first, then diffs one by one, then evaluation.

### Expected Gain
- First token appears in <2s (instead of waiting 30-60s for full response).
- Perceived latency drops by 70-80%.

---

## Option 9: Skip Evaluation for Low-Risk Changes

**Impact: MEDIUM | Effort: LOW | Risk: MEDIUM**

Not every code change needs critic+defender+controller (3 LLM calls, ~15-25s).

### What to Do
- **Heuristic skip:** If the generated diff is < 20 lines and touches only 1 file, skip evaluation.
- **User toggle:** Add `/generate --no-eval` flag or a setting `repopilot.skipEvaluation`.
- **Confidence-based:** If router confidence > 0.9 and primary action is GENERATE, skip evaluation.

### Expected Gain
- Saves 15–25s per request where evaluation is skipped.
- ~30-50% of generation requests are low-risk and could skip.

---

## Option 10: Ollama Concurrent Model Loading

**Impact: MEDIUM | Effort: LOW | Risk: LOW**

By default Ollama loads one model at a time. When switching between 1.5b (router) and 3b (generator), there's a swap delay.

### What to Do
- Set `OLLAMA_NUM_PARALLEL=4` — allows 4 concurrent requests.
- Set `OLLAMA_MAX_LOADED_MODELS=2` — keeps both models in memory simultaneously.
- Requires sufficient RAM/VRAM (3b ≈ 2GB, 1.5b ≈ 1GB → 3GB total).

### Expected Gain
- Eliminates 3–5s model swap delay between agent calls.

---

## Recommendation Matrix

| # | Option | Time Saved | Effort | Risk | Priority |
|---|--------|-----------|--------|------|----------|
| 1 | Model Warm-Keeping | 5–30s (first call) | 1 hour | None | **P0** |
| 6 | Persistent Index | 15–55s (repeat sessions) | 30 min | None | **P0** |
| 10 | Concurrent Model Loading | 3–5s per request | 10 min | None | **P0** |
| 7 | GPU Acceleration | 3x overall | 30 min | None | **P0** (if GPU available) |
| 4 | Reduce Token Count | 20-40% per call | 3 hours | Low | **P1** |
| 3 | Smaller Router Model (0.5b) | 2–3s per request | 2 hours | Medium | **P1** |
| 8 | Streaming Everywhere | 70-80% perceived | 6 hours | Low | **P1** |
| 5 | Semantic Cache | Instant for repeats | 4 hours | Low | **P2** |
| 2 | Pipeline Overlap | 8–15s per request | 4 hours | Low | **P2** |
| 9 | Skip Eval for Low-Risk | 15–25s per request | 2 hours | Medium | **P2** |

### Quick Wins (Implement in < 1 hour, massive impact)
1. **Set `OLLAMA_KEEP_ALIVE=24h`** — eliminates cold start.
2. **Set `OLLAMA_MAX_LOADED_MODELS=2`** — eliminates model swap.
3. **Set `USE_PERSISTENT_INDEX=True`** — eliminates re-indexing.
4. **Verify GPU is active** — 3x speed boost.

### Combined Best Case (All Quick Wins)
- First query: **5-10s** instead of 30-60s.
- Subsequent queries: **15-25s** instead of 40-90s.
- Repeat queries (cache): **<1s**.
- Perceived (with streaming): First token in **<2s**.

---

*Tell me which options you want to implement and I'll build them.*
