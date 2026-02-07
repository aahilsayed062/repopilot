# RepoPilot AI - Technical Architecture (Submission Version)

## System Objective

Provide repository-grounded engineering assistance with explainable, citation-backed answers and cautious generation.

## High-Level Flow

1. Load repository via `/repo/load`
2. Index repository via `/repo/index`
3. Retrieve relevant chunks for each query
4. Generate structured answer with citations and confidence

## Core Components

- `backend/app/services/repo_manager.py`: clone, file scan, repo stats
- `backend/app/services/indexer.py`: file selection, chunk embed/store, progress updates
- `backend/app/services/retriever.py`: semantic retrieval from Chroma collections
- `backend/app/services/planner.py`: optional query decomposition
- `backend/app/services/answerer.py`: grounded response formatting, citation validation, confidence logic
- `backend/app/services/generator.py`: repository-aligned code generation
- `backend/app/services/test_generator.py`: PyTest artifact generation

## Explainability Strategy

- Response structure is normalized into clear sections.
- Citations are validated against retrieved chunks.
- Confidence is calibrated from evidence coverage and uncertainty markers.
- Assumptions are surfaced when confidence is low.

## Frontend + Extension UX

- Progressive loading/indexing status percentages
- Citation rendering and confidence badges
- Generation output presentation (plan/diffs/tests)
- Greeting/casual-message handling for humane interaction

## Deployment Notes

- Backend Dockerized under `backend/Dockerfile`
- Frontend Dockerized under `frontend/Dockerfile`
- Frontend runtime output uses `.next-runtime` as configured in `frontend/next.config.ts`

## Submission References

- Summary and checklist: `docs/FINAL_SUBMISSION_PS7.md`
- Repo map: `docs/REPO_STRUCTURE.md`
- Demo runbook: `docs/DEMO_CHECKLIST.md`
