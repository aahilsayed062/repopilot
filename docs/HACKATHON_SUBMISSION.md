# RepoPilot Website - Hackathon Submission

## Branch

- Submit from: `website`

## Project Summary

RepoPilot Website analyzes any public GitHub repository and returns:
- architecture summary
- tech stack and key components
- file tree and stats
- dependency view and visual graphs

The experience is optimized for demos with live loading progress and deploy-ready frontend/backend split.

## Live Links

- Frontend: `https://frontend-azure-chi-43.vercel.app`
- Backend: `https://backend-delta-dun-69.vercel.app`
- Backend health: `https://backend-delta-dun-69.vercel.app/health`

## Tech Stack

- Frontend: Next.js 16, React 19, Tailwind
- Backend: FastAPI, Pydantic, httpx
- LLM: Gemini (`GEMINI_API_KEY`)
- Hosting: Vercel (frontend + backend)

## Key Implementation Details

1. GitHub repo ingestion supports two modes:
   - `git clone --depth 1` when `git` exists
   - ZIP archive fallback when `git` is unavailable (serverless-safe)
2. Configurable repo limits:
   - `MAX_REPO_SIZE_MB` default `250`
   - `CLONE_TIMEOUT_SECONDS` default `60`
3. Analyze UI includes real-time loading percentage and progress bar to avoid "stuck" perception.

## Local Run

### Backend
```bash
cd website/backend
pip install -r requirements.txt
copy .env.example .env
# set GEMINI_API_KEY
uvicorn app.main:app --reload --port 8001
```

### Frontend
```bash
cd website/frontend
npm install
npm run dev
```

## Demo Script (60-90 sec)

1. Open frontend URL.
2. Paste `https://github.com/vercel/next.js`.
3. Show live loading progress.
4. Walk through summary + graph + dependencies.
5. Mention backend health endpoint and serverless-safe clone fallback.
