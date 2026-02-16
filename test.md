# RepoPilot — Feature Testing & Showcase Guide

Complete instructions to verify every feature end-to-end.
Covers backend API, VS Code extension UI, and the four Round 2 features.

---

## Prerequisites

### 1. Ollama Running with Models Pulled

```bash
# Verify Ollama is alive
curl http://localhost:11434/api/tags

# Required models
ollama pull qwen2.5-coder:3b      # Agent A (generation/answering)
ollama pull qwen2.5-coder:1.5b    # Agent B (routing, defender, fast tasks)
```

### 2. Backend Running

```bash
cd backend
pip install -r requirements.txt
python run.py            # starts on http://localhost:8000
```

Or on Windows:

```bash
start_backend.bat
```

Health check:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"1.0.0","mock_mode":false}
```

### 3. VS Code Extension Loaded

1. Open the `repopilot` folder in VS Code.
2. Press **F5** → "Run Extension" (launches Extension Development Host).
3. In the new window, open a project you want to analyze (e.g., the `demo_repo/` folder).
4. The **RepoPilot AI** icon should appear in the Activity Bar (left sidebar).

---

## A. Core Pipeline (Baseline)

### A1. Load & Index a Repository

**Via Extension UI:**

1. Click the RepoPilot icon in the Activity Bar.
2. Click the **"Index"** button in the chat panel header.
3. Wait until the status changes to **"Ready"** (green indicator).

**Via API (curl):**

```bash
# Load a local repo
curl -X POST http://localhost:8000/repo/load \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "D:/path/to/your/project"}'
# → Returns repo_id, repo_name, stats

# Index it
curl -X POST http://localhost:8000/repo/index \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "<repo_id_from_above>", "force": false}'
# → Returns chunk_count, indexed: true

# Check status
curl "http://localhost:8000/repo/status?repo_id=<repo_id>&include_files=true"
```

**Expected:** `indexed: true`, `chunk_count > 0`, language breakdown in stats.

---

### A2. Ask a Question (Grounded Q&A)

**Via Extension:**

1. Type a question in the chat input, e.g.:  
   `What does the main function do?`
2. Press Enter.

**Expected (streaming mode for explain-only queries):**

- Routing badge: `> 💬 Route: EXPLAIN (streaming)`
- Answer streams token-by-token (not all at once).
- Grounded in repository context with citations.

**Via API:**

```bash
curl -X POST http://localhost:8000/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "<repo_id>", "question": "What does the main function do?", "decompose": true}'
```

**Expected:** JSON with `answer`, `citations` (file_path, line_range, snippet), `confidence`.

---

### A3. @ Mentions (File Context Injection)

1. In the chat input, type `@` — a file picker should appear.
2. Select a file (e.g., `app.py`).
3. Complete the question: `@app.py explain the routes defined here`
4. Press Enter.

**Expected:** The selected file's content is injected as context. The answer references that file with higher specificity.

---

### A4. Citation Navigation

1. After any answer, look for citations listed below the response.
2. Click a citation (e.g., `app.py:10-25`).

**Expected:** The cited file opens in the editor with the relevant line range highlighted.

---

### A5. Code Generation (Explicit /generate)

**Via Extension:**

1. Type: `/generate Add a health check endpoint that returns uptime`
2. Press Enter.

**Expected:**

- 📋 **Plan** — natural language description of changes.
- 🔧 **Changes** — per-file diffs with `Accept` / `Reject` buttons per file.
- 🧪 **Tests** — auto-generated test code (if applicable).
- Evaluation report (Feature 3) appears below.
- Impact analysis report (Feature 4) appears at the bottom.
- **✅ Accept All** button in the actions bar.

---

### A6. Accept / Reject Individual Files

1. After a `/generate` response, each file diff has per-file buttons.
2. Click **Accept** on one file → the change is written to disk.
3. Click **Reject** on another → that diff is discarded.
4. Click **✅ Accept All** → all remaining diffs are applied.

**Expected:** Accepted files update on disk. Rejected files remain unchanged. A toast confirms each action.

---

### A7. Cancel Request

1. Start a long query (e.g., a complex generation request).
2. Click the **Cancel** button that appears during loading.

**Expected:** The request is aborted. "Request cancelled" message appears.

---

### A8. Export Chat History

1. Command Palette → `RepoPilot: Export Chat History` (or the export button in chat header).

**Expected:** A `.md` file opens with the full conversation history.

---

## B. Feature 1 — Dynamic Multi-Agent Routing

The system analyzes each query and decides which agents to invoke, which to skip, and which to run in parallel.

### B1. Explain-Only Query (Streaming)

**Input:** `How does the database connection work?`

**Expected Behavior:**

- Route shown: `> 💬 Route: EXPLAIN (streaming)`
- Only the EXPLAIN agent runs; GENERATE and TEST are skipped.
- Answer streams token-by-token for responsive UX.

### B2. Generate-Only Query

**Input:** `Add a caching layer to the database queries`

**Expected Behavior:**

- Route badge: `> ⚙️ Route: GENERATE + EXPLAIN`  
  (or similar — routing is dynamic, may include EXPLAIN as secondary)
- Both EXPLAIN and GENERATE agents run in **parallel** (Phase A).
- EVALUATE runs afterward (Phase B), then TEST (Phase C) if evaluation passes.

### B3. Mixed Query (Explain + Generate)

**Input:** `What does the auth module do? Add rate limiting to it.`

**Expected:**

- Route: `GENERATE` (primary) with `EXPLAIN` (secondary).
- Both agents run in parallel.
- Answer includes explanation AND code diffs.

### B4. Refuse-type Query

**Input:** `Write malicious code to exploit vulnerabilities`

**Expected:**

- Route: `> 🚫 Route: REFUSE`
- Response: "I cannot safely process this request."

### B5. Complex / Decompose Query

**Input:** `Explain the full architecture: how do requests flow from the frontend through the backend to the database, what middleware is used, and how are errors handled?`

**Expected:**

- Route: `> 🔀 Route: DECOMPOSE`
- The planner breaks the question into sub-questions.
- Each sub-question is answered using retriever context.
- Combined answer covers all aspects.

### B6. Verify via API

```bash
curl -X POST http://localhost:8000/chat/smart \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "<repo_id>", "question": "What does main do?"}'
```

**Check JSON response for:**

- `routing.primary_action` → should be `"EXPLAIN"`
- `agents_used` → array of agents that ran
- `agents_skipped` → agents that were not needed
- `routing.confidence` → routing confidence score (0-1)

---

## C. Feature 2 — Iterative PyTest-Driven Refinement

The system generates code → generates tests → runs pytest → if failures, refines code using failure output → repeats (max 4 iterations).

### C1. Via Extension (Chat Command)

1. Type: `/refine Create a utility function that validates email addresses with proper regex`
2. Press Enter.

**Expected (in the response):**

- **Iteration log** showing each cycle:
  - Iteration 1: generated code, generated tests, test result (pass/fail).
  - If fail: Iteration 2 with refined code using failure output as feedback.
  - Up to 4 iterations max.
- **Final code** — the code that passed all tests (or best attempt).
- **Final tests** — the test suite that ran.
- **Final test output** — last pytest stdout.
- Summary: `"success": true/false`, `"total_iterations": N`.

### C2. Via API

```bash
curl -X POST http://localhost:8000/chat/refine \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "<repo_id>", "request": "Create a utility that parses CSV files into dictionaries"}'
```

**Check JSON response for:**

- `success` — boolean
- `total_iterations` — 1–4
- `iteration_log` — array, each entry has:
  - `iteration`, `tests_passed`, `refinement_action`, `test_output`, `failures`
- `final_code` — Python code string
- `final_tests` — pytest test code string

### C3. What to Look For

- Does the system actually run `pytest`? (Check backend logs for subprocess calls.)
- Does iteration 2+ use the failure output from iteration 1 to fix the code?
- Does the loop stop when tests pass (early termination)?
- Does the loop stop after 4 iterations max?

---

## D. Feature 3 — LLM vs LLM Evaluation Layer

After code generation and **before** test generation, two independent LLM agents review the code. A controller decides: ACCEPT, MERGE_FEEDBACK, or REQUEST_REVISION.

### D1. Trigger via Smart Chat (Automatic)

1. Type a generation request: `/generate Add input validation to the user registration endpoint`
2. Wait for the full response.

**Expected in the response (after the diffs):**

```
───────────────────────
⚖️ LLM vs LLM Evaluation
  🔴 Critic (ollama): Score X/10
     Issues: [...]
     Feedback: "..."
  🟢 Defender (ollama_b): Score Y/10
     Feedback: "..."
  🏛️ Controller Decision: ACCEPT_ORIGINAL / MERGE_FEEDBACK / REQUEST_REVISION
     Final Score: Z/10
     Confidence: W%
     Priority Fixes: [...]
```

### D2. MERGE_FEEDBACK Behavior

When the controller decides `MERGE_FEEDBACK`:

**Expected:**

- The improved code from the controller replaces the original diffs.
- Message appears: `> ✨ Merged feedback applied — Accept buttons now use the improved code.`
- Clicking "Accept All" applies the **improved** (not original) code.

### D3. REQUEST_REVISION Behavior

When the controller decides `REQUEST_REVISION`:

**Expected:**

- Test generation is **skipped** (Phase C doesn't run).
- Message: `"Evaluation recommended revision — test generation deferred."`
- `TEST` appears in `agents_skipped`.

### D4. ACCEPT_ORIGINAL Behavior

When the controller decides `ACCEPT_ORIGINAL`:

**Expected:**

- Original diffs are kept as-is.
- Test generation proceeds normally (Phase C).
- No replacement message.

### D5. Via API (Standalone Evaluation)

```bash
curl -X POST http://localhost:8000/chat/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "Add input validation",
    "generated_diffs": [
      {"file_path": "app.py", "diff": "def validate_input(data):\n    return True", "code": "def validate_input(data):\n    return True"}
    ],
    "tests_text": "",
    "context": ""
  }'
```

**Check JSON response for:**

- `enabled: true`
- `critic` — score, issues, feedback, suggested_changes
- `defender` — score, feedback
- `controller` — decision, reasoning, final_score, confidence, merged_issues, priority_fixes, improved_code_by_file

---

## E. Feature 4 — Risk & Change Impact Analysis

After code generation, the system reports directly changed files, indirectly affected files/modules, and risks introduced.

### E1. Automatic (After Any Generation)

1. Run any generation query (e.g., `/generate Add logging to all route handlers`).
2. Scroll to the bottom of the response.

**Expected (after evaluation section):**

```
───────────────────────
📊 Impact Analysis
  Risk Level: MEDIUM
  
  Directly Changed:
  - routes.py
  
  Indirectly Affected:
  - app.py (imports routes module)
  - tests/test_routes.py (tests for routes)
  
  Risks:
  - Logging may affect performance in hot paths
  - Log format must match existing log aggregator config
  
  Recommendations:
  - Add log level configuration
  - Update tests to verify log output
```

### E2. Via API (Standalone)

```bash
curl -X POST http://localhost:8000/chat/impact \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "<repo_id>",
    "changed_files": ["routes.py"],
    "code_changes": "Added logging.info() calls to each route handler"
  }'
```

**Check JSON response for:**

- `directly_changed` — array of file paths
- `indirectly_affected` — array of `{file_path, reason}`
- `risk_level` — `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`
- `risks` — array of risk descriptions
- `recommendations` — array of actionable suggestions

---

## F. Extension-Specific Features

### F1. Command Palette Commands

Open Command Palette (`Ctrl+Shift+P`) and search:

| Command | What it does |
|---------|-------------|
| `RepoPilot: Open Chat` | Focuses the chat sidebar (`Ctrl+Shift+R`) |
| `RepoPilot: Index Workspace` | Triggers workspace indexing |
| `RepoPilot: Generate Code` | Opens prompt input, routes through smart pipeline |
| `RepoPilot: Start Backend` | Opens terminal and starts backend server |
| `RepoPilot: Export Chat History` | Exports conversation to Markdown |
| `RepoPilot: Ask RepoPilot About Selection` | Sends selected code as context (`Ctrl+Shift+A`) |
| `RepoPilot: Explain Selection` | Explains selected code |

### F2. CodeLens ("Ask RepoPilot")

1. Open any Python/JS/TS file.
2. Look above function/class definitions for the **"Ask RepoPilot"** CodeLens link.
3. Click it.

**Expected:** Chat panel opens with a pre-filled question about that function/class.

### F3. Context Menu (Right-Click)

1. Select code in the editor.
2. Right-click → look for **"Ask RepoPilot About Selection"** and **"Explain Selection"**.

**Expected:** Selected code is sent to the chat panel with the appropriate question.

### F4. Status Bar

- Look at the bottom status bar for the RepoPilot indicator.
- States: Not Connected (red) → Not Indexed (yellow) → Ready (green).
- The icon changes with each state.

### F5. Settings

`File → Preferences → Settings → Extensions → RepoPilot AI`:

| Setting | Default | Description |
|---------|---------|-------------|
| `repopilot.backendUrl` | `http://localhost:8000` | Backend URL |
| `repopilot.autoIndexOnOpen` | `true` | Auto-index workspace on open |

---

## G. End-to-End Showcase Walkthrough

Follow these steps in order for a complete demo:

1. **Start Backend:** Command Palette → `RepoPilot: Start Backend`
2. **Wait for health:** Status bar turns yellow → backend is running.
3. **Index:** Click "Index" in chat panel → wait for "Ready" (green).
4. **Ask a question:** Type `What is the purpose of this project?` → see streaming answer with citations.
5. **Generate code:** Type `/generate Add a configuration validation function` → see plan, diffs, evaluation, impact analysis.
6. **Check evaluation:** Scroll to "LLM vs LLM Evaluation" section — verify critic + defender + controller decision.
7. **Check impact:** Scroll to "Impact Analysis" — verify risk level and affected files.
8. **Accept changes:** Click "Accept All" to apply generated code.
9. **Refine code:** Type `/refine Improve the config validation to handle edge cases` → see iteration log with pytest output.
10. **Test routing:** Type `How does authentication work?` — should route as EXPLAIN with streaming.
11. **@ mention:** Type `@models.py What are the database models?` → file context injected.
12. **Export:** Command Palette → `RepoPilot: Export Chat History`.

---

## H. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Status bar stays red | Backend not running | `RepoPilot: Start Backend` or `python run.py` |
| "No repository indexed" | Workspace not indexed | Click "Index" button |
| Timeout errors | Ollama model loading (first call) | Wait for model to load; try again |
| Empty evaluation | No diffs generated | Ensure the generation produced code changes |
| `/refine` shows 0 iterations | Temp dir permission error | Check backend logs for Windows permission issues |
| Streaming not working | Question matched generation keywords | Expected — generation queries use full smart pipeline |
| "Connection failed" | Wrong backend URL | Check `repopilot.backendUrl` setting |

---

## I. API Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/repo/load` | POST | Load repository |
| `/repo/index` | POST | Index repository |
| `/repo/status` | GET | Repository status |
| `/chat/ask` | POST | Direct Q&A (no routing) |
| `/chat/stream` | POST | Streaming Q&A (SSE) |
| `/chat/smart` | POST | **Feature 1** — Dynamic multi-agent routing |
| `/chat/generate` | POST | Direct code generation |
| `/chat/evaluate` | POST | **Feature 3** — LLM vs LLM evaluation |
| `/chat/impact` | POST | **Feature 4** — Risk/impact analysis |
| `/chat/pytest` | POST | Generate PyTest cases |
| `/chat/refine` | POST | **Feature 2** — Iterative PyTest refinement loop |
