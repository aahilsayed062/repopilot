# RepoPilot AI — Complete Setup & Testing Guide

> **One document to go from zero to fully running in under 15 minutes.**

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Install & Configure Ollama (LLM Server)](#3-install--configure-ollama-llm-server)
4. [Backend Setup (FastAPI)](#4-backend-setup-fastapi)
5. [Environment Configuration (.env)](#5-environment-configuration-env)
6. [Frontend Setup (Next.js)](#6-frontend-setup-nextjs)
7. [VS Code Extension Setup](#7-vs-code-extension-setup)
8. [Starting Everything](#8-starting-everything)
9. [Testing Every Feature](#9-testing-every-feature)
10. [API Reference (Quick)](#10-api-reference-quick)
11. [What Has Been Implemented](#11-what-has-been-implemented)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.10+ | Backend server |
| **Node.js** | 18+ | Frontend & VS Code extension |
| **Git** | 2.30+ | Repo cloning |
| **Ollama** | Latest | Local LLM inference (primary AI engine) |
| **VS Code** | 1.85+ | Extension host (optional — can use frontend instead) |

### Hardware Recommendations

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| Disk | 5 GB free | 10 GB free |
| GPU | Not required | NVIDIA with 4GB+ VRAM (much faster) |
| CPU | 4 cores | 8 cores |

---

## 2. Clone the Repository

```bash
git clone <repo-url> RepoPilot
cd RepoPilot
```

Your folder structure should look like:
```
RepoPilot/
├── .env                  # Environment config (create this)
├── backend/              # FastAPI Python server
├── frontend/             # Next.js React web app
├── vscode-extension/     # VS Code sidebar chat
├── demo_repo/            # Sample repo for testing
└── tests/                # Verification scripts
```

---

## 3. Install & Configure Ollama (LLM Server)

### Step 1: Install Ollama

**Windows:**
```
Download from https://ollama.com/download/windows
Run the installer → Ollama starts automatically as a system service
```

**macOS:**
```bash
brew install ollama
ollama serve    # Start the server
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve    # Start the server
```

### Step 2: Pull Required Models

Open a terminal and run these commands one by one:

```bash
# Primary coding model (1.5B params, ~986 MB) — Used for all general tasks
ollama pull qwen2.5-coder:1.5b

# Secondary coding model (3B params, ~1.9 GB) — Used for complex tasks & evaluation
ollama pull qwen2.5-coder:3b

# Ultra-fast router model (0.5B params, ~397 MB) — Used ONLY for query classification
ollama pull qwen2.5-coder:0.5b

# Embedding model (45 MB) — Used for semantic search / vector indexing
ollama pull all-minilm
```

### Step 3: Verify Models Are Loaded

```bash
ollama list
```

Expected output:
```
NAME                    SIZE
qwen2.5-coder:0.5b     397 MB
qwen2.5-coder:1.5b     986 MB
qwen2.5-coder:3b       1.9 GB
all-minilm:latest       45 MB
```

### Step 4: Verify Ollama Is Running

```bash
curl http://localhost:11434/api/tags
```

You should get a JSON response listing your models.

> **Tip:** On Windows, Ollama runs as a background service automatically. On Linux/macOS, keep `ollama serve` running in a separate terminal.

---

## 4. Backend Setup (FastAPI)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
.\venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
python -c "from app.config import settings; print('Config OK:', settings.app_name)"
```

Expected: `Config OK: RepoPilot AI`

---

## 5. Environment Configuration (.env)

Create a `.env` file in the **project root** (NOT inside `backend/`):

```bash
# Copy this entire block into .env
# =============================================================================
# RepoPilot AI - Environment Configuration
# =============================================================================

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Ollama (Primary — local, offline, unlimited)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_A=qwen2.5-coder:1.5b
OLLAMA_MODEL_B=qwen2.5-coder:3b
OLLAMA_EMBED_MODEL=all-minilm

# Google Gemini (Optional fallback — free tier)
# Get key: https://aistudio.google.com/apikey
# GEMINI_API_KEY=your_key_here
# GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001
# GEMINI_CHAT_MODEL=gemini-2.0-flash

# Data directory
DATA_DIR=data
```

> **Note:** Ollama is the primary provider. Gemini/OpenAI are optional fallbacks. The system works fully offline with just Ollama.

---

## 6. Frontend Setup (Next.js)

```bash
cd frontend
npm install
```

That's it — the frontend has no special configuration needed.

---

## 7. VS Code Extension Setup

```bash
cd vscode-extension
npm install
npm run compile    # or: npx webpack --mode development
```

### Load in VS Code

1. Open VS Code
2. Press `F5` (or Run → Start Debugging)
3. Select "VS Code Extension Development Host"
4. In the new VS Code window, look for the **RepoPilot AI** icon in the Activity Bar (left sidebar)

### Extension Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `repopilot.backendUrl` | `http://localhost:8000` | Backend server URL |
| `repopilot.autoIndexOnOpen` | `true` | Auto-index when workspace opens |

---

## 8. Starting Everything

### Option A: Manual Start (Recommended for Development)

**Terminal 1 — Ollama** (skip on Windows, it's a service):
```bash
ollama serve
```

**Terminal 2 — Backend:**
```bash
cd backend
.\venv\Scripts\Activate.ps1    # Windows
# source venv/bin/activate     # Linux/macOS
python run.py
```
You'll see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```
On startup, the backend will:
- Pre-warm all Ollama models (loads them into VRAM)
- Start a background heartbeat (pings Ollama every 4 minutes to keep models loaded)

**Terminal 3 — Frontend:**
```bash
cd frontend
npm run dev
```
Opens at `http://localhost:3000`

**Terminal 4 — VS Code Extension:**
Press `F5` in the `vscode-extension` folder.

### Option B: Quick Start Script (Windows)

```bash
.\start_backend.bat
```

This activates the venv and launches the backend.

### Verify Everything Is Running

```bash
# Backend health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"0.1.0","mock_mode":false}
```

Open `http://localhost:8000/docs` for the interactive Swagger UI.

---

## 9. Testing Every Feature

### A. Load & Index a Repository

#### Via Frontend (http://localhost:3000):
1. Paste a GitHub URL in the input field (e.g., `https://github.com/user/repo`)
2. Click **Load** — wait for cloning + indexing (progress bar shows %)
3. Once complete, the chat input activates

#### Via API (curl):
```bash
# Step 1: Load
curl -X POST http://localhost:8000/repo/load \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repo"}'
# → Returns { repo_id: "abc123..." }

# Step 2: Index
curl -X POST http://localhost:8000/repo/index \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "abc123..."}'
# → Returns { chunk_count: 1500, indexed: true }
```

#### Via VS Code Extension:
1. Open any workspace folder
2. Run command: `RepoPilot: Index Workspace` (Ctrl+Shift+P)
3. Watch the status bar for progress

---

### B. Feature 1 — Dynamic Multi-Agent Routing (`/chat/smart`)

This is the **main endpoint**. It analyzes your query and automatically decides which agents to use.

**Test queries:**
```bash
# Simple explanation (routes to EXPLAIN only)
curl -X POST http://localhost:8000/chat/smart \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "YOUR_ID", "question": "How does authentication work?"}'

# Code generation (routes to GENERATE + TEST in parallel)
curl -X POST http://localhost:8000/chat/smart \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "YOUR_ID", "question": "Add input validation to the login endpoint"}'

# Test generation (routes to TEST only)
curl -X POST http://localhost:8000/chat/smart \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "YOUR_ID", "question": "Write tests for the user model"}'

# Complex query (routes to DECOMPOSE → EXPLAIN)
curl -X POST http://localhost:8000/chat/smart \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "YOUR_ID", "question": "Explain the complete authentication flow from login to JWT validation including how middleware checks tokens and what happens on expiry"}'
```

**What to check in the response:**
- `routing.primary_action` tells you which agent was selected
- `routing.reasoning` explains why
- `agents_used` and `agents_skipped` show the execution plan
- `_from_cache: true` appears on cache hits (repeat same query)

---

### C. Feature 2 — Iterative PyTest-Driven Refinement (`/chat/refine`)

```bash
curl -X POST http://localhost:8000/chat/refine \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "YOUR_ID",
    "question": "Create a function to validate email addresses with proper error handling",
    "max_iterations": 3
  }'
```

**What to check:**
- `iterations[]` — each iteration shows: generated code → generated tests → pytest output → pass/fail
- `final_code` — the refined version that passes all tests
- `total_iterations` — how many loops it took
- The loop stops when tests pass OR after max iterations

**In Frontend:** Type `/refine Add a rate limiter middleware` in the chat.

**In VS Code:** Right-click code → "Generate with Refinement" or type in chat.

---

### D. Feature 3 — LLM vs LLM Evaluation (`/chat/evaluate`)

This runs automatically inside `/chat/smart` when code is generated. To test directly:

```bash
curl -X POST http://localhost:8000/chat/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "YOUR_ID",
    "question": "Add caching to the database queries",
    "code_diffs": [{"file_path": "db.py", "diff": "def cached_query(q):\n    return cache.get(q) or db.execute(q)"}]
  }'
```

**What to check:**
- `critic` — Independent critique (issues, concerns)
- `defender` — Independent defense (strengths, improvements)
- `controller.decision` — One of:
  - `ACCEPT_ORIGINAL` — Code is good as-is
  - `MERGE_FEEDBACK` — Code accepted with improvements applied
  - `REQUEST_REVISION` — Code needs significant changes (blocks test generation)
- `controller.improved_code_by_file` — Merged improvements (when MERGE_FEEDBACK)

---

### E. Feature 4 — Risk & Change Impact Analysis (`/chat/impact`)

```bash
curl -X POST http://localhost:8000/chat/impact \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "YOUR_ID",
    "question": "What is the impact of changing the database schema?",
    "changed_files": ["models.py", "database.py"]
  }'
```

**What to check:**
- `affected_files[]` — Files directly and indirectly impacted
- `risk_level` — LOW / MEDIUM / HIGH / CRITICAL
- `risks[]` — Specific risks identified
- `recommendations[]` — Suggested mitigations

**In Frontend:** Impact analysis runs **automatically** after any code generation.

---

### F. Streaming Q&A (`/chat/stream`)

```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "YOUR_ID", "question": "What does this project do?"}'
```

Returns Server-Sent Events (SSE) — you'll see chunks arriving in real-time.

---

### G. End-to-End Workflow Test

1. **Load repo** → paste `https://github.com/some/repo` in Frontend
2. **Wait for index** → progress bar fills to 100%
3. **Ask a question** → "How does the main function work?" — see grounded answer with citations
4. **Generate code** → "Add input validation to the login function" — see diffs + evaluation + impact
5. **Refine** → `/refine Add email validation` — watch the test loop iterate
6. **Check cache** → Ask the same question again — instant response (`_from_cache: true`)

---

## 10. API Reference (Quick)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check |
| POST | `/repo/load` | Clone/load repository |
| GET | `/repo/status?repo_id=X` | Get repo info & progress |
| POST | `/repo/index` | Trigger indexing |
| POST | `/chat/ask` | Standard Q&A |
| POST | `/chat/stream` | Streaming Q&A (SSE) |
| POST | `/chat/smart` | **Main endpoint** — dynamic routing |
| POST | `/chat/generate` | Code generation |
| POST | `/chat/pytest` | Test generation |
| POST | `/chat/evaluate` | LLM vs LLM evaluation |
| POST | `/chat/impact` | Risk analysis |
| POST | `/chat/refine` | Iterative refinement loop |

All chat endpoints accept:
```json
{
  "repo_id": "string (required)",
  "question": "string (required)",
  "chat_history": [{"role": "user|assistant", "content": "..."}],
  "context_file_hints": ["path/to/file.py"]
}
```

Full interactive docs: `http://localhost:8000/docs`

---

## 11. What Has Been Implemented

### Core Pipeline (100%)

| Component | Status | Details |
|-----------|--------|---------|
| Repository Loading | ✅ Done | GitHub clone (shallow, filtered), local path loading |
| File Scanning | ✅ Done | 50+ extensions, smart filtering, size limits |
| Code Chunking | ✅ Done | Language-aware: code (by lines), docs (by paragraphs), config (whole file) |
| Embedding Generation | ✅ Done | Ollama all-minilm (384d), Gemini fallback (768d), batch processing |
| Vector Storage | ✅ Done | ChromaDB with cosine similarity, ephemeral + persistent modes |
| Semantic Retrieval | ✅ Done | Hybrid reranking: 70% lexical + 30% semantic |
| Grounded Q&A | ✅ Done | Evidence-based answers with citations (file, line range, snippet) |
| Streaming Responses | ✅ Done | SSE for real-time token output |
| Code Generation | ✅ Done | Context-aware diffs with plan + file changes |
| Test Generation | ✅ Done | PyTest with style matching from existing tests |

### Round 2 Features (100%)

| Feature | Status | Details |
|---------|--------|---------|
| F1: Multi-Agent Routing | ✅ Done | 0.5b router → 1.5b fallback → heuristic. Skip/parallel/chain agents. |
| F2: PyTest Refinement Loop | ✅ Done | Max 4 iterations. Generate → test → fix → repeat until green. |
| F3: LLM vs LLM Evaluation | ✅ Done | Critic + Defender in parallel → Controller merges. 3 decisions. |
| F4: Impact Analysis | ✅ Done | Direct + indirect file impact, risk levels, recommendations. |

### Speed Optimizations (100%)

| Optimization | Status | Impact |
|-------------|--------|--------|
| Model Warm-Keeping | ✅ Done | keep_alive=24h, prewarm on startup, heartbeat every 4 min |
| Pipeline Overlap | ✅ Done | Eval + test generation run speculatively in parallel |
| 0.5b Router Model | ✅ Done | ~200ms routing (vs 2-4s with 3b model) |
| Semantic Response Cache | ✅ Done | TTL-based, commit-hash keyed, auto-invalidate on re-index |
| Persistent Index | ✅ Done | Commit-hash staleness, skip re-index when fresh |

### Interfaces (100%)

| Interface | Status | Details |
|-----------|--------|---------|
| FastAPI Backend | ✅ Done | 12 endpoints, Swagger UI, CORS, structured logging |
| Next.js Frontend | ✅ Done | Glass morphism UI, real-time progress, auto-impact, chat export |
| VS Code Extension | ✅ Done | Sidebar chat, CodeLens, Code Actions, status bar, file apply |

### LLM Provider Support

| Provider | Status | Use Case |
|----------|--------|----------|
| Ollama (Primary) | ✅ Active | All inference — 0.5b/1.5b/3b models |
| Gemini | ✅ Available | Fallback for chat + defender agent |
| OpenAI/Groq | ✅ Available | Optional fallback |
| Mock | ✅ Available | Development without any LLM |

---

## 12. Troubleshooting

### Ollama Not Found

```
Error: Ollama not available
```
**Fix:** Ensure Ollama is running:
```bash
# Windows: Check system tray for Ollama icon
# Linux/macOS:
ollama serve
```

### Models Not Loaded

```
Error: ollama_no_models
```
**Fix:** Pull the required models:
```bash
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:3b
ollama pull qwen2.5-coder:0.5b
ollama pull all-minilm
```

### Backend Won't Start

```
ModuleNotFoundError: No module named 'pydantic_settings'
```
**Fix:** Activate venv and install deps:
```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Frontend: "Cannot connect to backend"

**Fix:** Ensure backend is running on port 8000:
```bash
curl http://localhost:8000/health
```

### VS Code Extension: "Backend not available"

**Fix:** Check the setting `repopilot.backendUrl` is set to `http://localhost:8000`.

### Indexing Takes Too Long

The default limits are already tuned for speed:
- Max 900 files, 2500 chunks, 55-second time budget
- Top-priority files are indexed first (code > config > docs)

If still slow, reduce in `.env`:
```
INDEX_MAX_FILES=500
INDEX_MAX_CHUNKS=1500
INDEX_TIME_BUDGET_SECONDS=30
```

### First Query Is Slow

The first query after startup may take 5-10 seconds while the model loads into GPU/RAM. Subsequent queries should be 15-25 seconds. Cached queries return in < 1 second.

### GPU vs CPU

Ollama auto-detects your GPU. To verify:
```bash
ollama ps
# Shows which model is loaded and whether GPU layers are used
```

For **NVIDIA GPU** acceleration, install the CUDA version of Ollama (included by default on Windows/macOS).

---

*Last updated: February 2026*
