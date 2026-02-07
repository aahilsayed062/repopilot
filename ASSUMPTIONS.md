# RepoPilot AI - Assumptions and Constraints

## Repository Assumptions

- A target repository can be cloned via Git over HTTPS.
- Useful project context exists in source/config/docs files inside the repository.
- Repository is treated as the source of truth for grounded answers.

## Runtime and Build Assumptions

- Backend: Python 3.11+ and required packages from `backend/requirements.txt`
- Frontend: Node.js 20+ and dependencies from `frontend/package.json`
- Extension workflow assumes VS Code environment for extension host testing

## Config Constraints (Current Defaults)

Source: `backend/app/config.py`

- `MAX_REPO_SIZE_MB=512`
- `MAX_FILES=10000`
- `CLONE_TIMEOUT_SECONDS=900`
- `INDEX_MAX_FILES=900`
- `INDEX_MAX_FILE_SIZE_KB=256`
- `INDEX_MAX_TOTAL_MB=20`
- `INDEX_MAX_CHUNKS=2500`
- `INDEX_TIME_BUDGET_SECONDS=55`

These defaults intentionally favor fast indexing and predictable latency.

## Grounding Policy

- Answers must be grounded in retrieved repository chunks.
- Citations include file path and line range.
- If evidence is insufficient, system returns low-confidence response with explicit limitations.

## Round-1 Constraint Alignment

- No mandatory runtime code execution for answer generation.
- PyTest artifacts are generated, not automatically executed as part of core flow.
- External knowledge is not treated as primary truth over repository evidence.

## Known Limits

- Retrieval is primarily semantic; exact-symbol lookup can still miss edge cases.
- Extremely large repositories may be partially indexed due to time/chunk budget controls.
- Provider rate limits can degrade responsiveness during heavy usage.

## Non-Required Items (Per PS guidance)

- Production-grade CI/CD is not required for acceptance.
- Perfect, zero-hallucination behavior is not assumed; safe refusal and confidence signaling are used instead.
