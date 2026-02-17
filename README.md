# RepoPilot Website (Hackathon Submission)

This branch (`website`) ships the standalone RepoPilot website:
- Frontend: `website/frontend` (Next.js)
- Backend: `website/backend` (FastAPI + Gemini)

## Live Deployment

- Frontend (public): `https://frontend-azure-chi-43.vercel.app`
- Backend API: `https://backend-delta-dun-69.vercel.app`
- Health check: `https://backend-delta-dun-69.vercel.app/health`

## What It Does

1. User submits a public GitHub repo URL.
2. Backend fetches repository source (supports environments without `git`).
3. System analyzes structure + key files.
4. Gemini generates architecture insights.
5. Frontend renders summary, graphs, and file/dependency views.

## Quick Local Run

### Backend

```bash
cd website/backend
pip install -r requirements.txt
copy .env.example .env
# set GEMINI_API_KEY in .env
uvicorn app.main:app --reload --port 8001
```

### Frontend

```bash
cd website/frontend
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Key Notes for Judges

- Analyze flow includes real-time progress percentage.
- Backend is deployed with Gemini key configured.
- Repository fetch supports fallback archive download when `git` binary is unavailable.
- Default repository size limit is now `250MB` (configurable with `MAX_REPO_SIZE_MB`).

## Submission Docs

- `docs/HACKATHON_SUBMISSION.md` (primary)
- `docs/DEMO_CHECKLIST.md`
- `website/website.md` (product/architecture notes)
