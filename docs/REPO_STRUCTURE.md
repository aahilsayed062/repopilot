# Repository Structure

## Top-Level

- `backend/`: FastAPI application and RAG services
- `frontend/`: Next.js web client
- `vscode-extension/`: extension-side client
- `tests/`: verification scripts
- `docs/`: final submission documentation
- `data/`, `index/`, `logs/`: runtime/generated artifacts

## Backend Layout

- `backend/app/routes/`: HTTP endpoints (`repo`, `chat`, `health`)
- `backend/app/services/`: ingestion/index/retrieval/generation services
- `backend/app/models/`: request/response schemas
- `backend/app/utils/`: logger, embeddings, LLM adapters

## Frontend Layout

- `frontend/src/app/page.tsx`: main application UI
- `frontend/src/app/globals.css`: design system + component styles
- `frontend/next.config.ts`: Next config (includes runtime distDir)
- `frontend/start.mjs`: production startup wrapper

## Extension Layout

- `vscode-extension/src/`: extension entry + chat panel integration
- `vscode-extension/media/`: webview resources

## Submission Docs

- `docs/FINAL_SUBMISSION_PS7.md`: asked vs done + extras
- `docs/DEMO_CHECKLIST.md`: walkthrough for evaluators
- `REPOPILOT_ASSESSMENT.md`: assessment summary
- `ASSUMPTIONS.md`: assumptions and constraints
- `EXPLAIN.md`: technical architecture summary
