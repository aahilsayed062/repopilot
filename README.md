# RepoPilot AI

Repository-grounded engineering assistant for **PS7**.

## Submission Snapshot

- Team: **AlphaByte 3.0**
- Problem Statement: **PS7 - RepoPilot AI (Repository-Grounded Assistant)**
- Core stack: `FastAPI` + `ChromaDB` + `Next.js` + `VS Code extension`
- Grounding: answers must include repository citations (`file_path` + `line_range`)

## What This Repo Contains

- `backend/`: ingestion, indexing, retrieval, grounded answer generation, code/test generation APIs
- `frontend/`: web client for repository connect, indexing, grounded Q&A, generation UI
- `vscode-extension/`: extension client for editor workflow
- `tests/`: verification scripts for project-level behavior checks
- `docs/`: final submission documentation bundle

## Quick Start (Local)

### 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Git

### 2. Configure environment

```bash
copy .env.example .env
```

Set required keys in `.env`:

- `GEMINI_API_KEY` (or OpenAI embeddings)
- `OPENAI_API_KEY` with Groq-compatible base URL (as configured)

### 3. Run backend

```bash
start_backend.bat
```

Backend health: `http://localhost:8000/health`

### 4. Run frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`

## API Surface

- `POST /repo/load`
- `GET /repo/status`
- `POST /repo/index`
- `POST /chat/ask`
- `POST /chat/generate`
- `POST /chat/pytest`

## Final Submission Docs

- `docs/FINAL_SUBMISSION_PS7.md`
- `docs/REPO_STRUCTURE.md`
- `docs/DEMO_CHECKLIST.md`
- `REPOPILOT_ASSESSMENT.md`
- `ASSUMPTIONS.md`
- `EXPLAIN.md`

## Notes

- Deployability is included but not relied upon for PS7 evaluation.
- Grounding and explainability are the primary acceptance criteria.
