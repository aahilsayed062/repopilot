# RepoPilot AI

A repository-grounded engineering assistant that provides answers, generates code, and writes tests **only when supported by evidence** from the target codebase.

## Core Principle

**Grounded-first, generate-second.**

All answers are grounded in repository evidence. If evidence is missing or conflicting, the system refuses safely and explains what's missing.

## Features

- 🔍 **Repo Ingestion** - Load from GitHub URL or local path
- 📊 **Smart Indexing** - Chunking + embeddings + vector store
- 💬 **Grounded Q&A** - Answers with citations (file path + line range)
- 🧩 **Query Decomposition** - Breaks complex questions into sub-queries
- ✨ **Code Generation** - Style-matched code + tests (only on explicit request)
- 🛡️ **Safe Refusal** - Refuses when evidence is missing or conflicting

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Git

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd repopilot

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Unix/macOS)
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your OpenAI API key (optional - mock mode works without it)
```

### Run Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### Run Frontend

```bash
cd frontend
npm install
npm run dev
```

### Verify Installation

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"0.1.0","mock_mode":true}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/repo/load` | POST | Load a repository |
| `/repo/status` | GET | Get repo stats |
| `/repo/index` | POST | Index a repository |
| `/chat/ask` | POST | Ask a question |
| `/chat/generate` | POST | Generate code/tests |

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | (mock mode if empty) |
| `OPENAI_CHAT_MODEL` | Chat model | gpt-4o |
| `DATA_DIR` | Data directory | data |
| `DEBUG` | Debug mode | false |

## Mock Mode

If no `OPENAI_API_KEY` is set, the system runs in mock mode:
- Uses deterministic fake embeddings
- Useful for testing without API costs

## Project Structure

```
repopilot/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── main.py    # App entry point
│   │   ├── config.py  # Settings
│   │   ├── routes/    # API endpoints
│   │   ├── services/  # Core logic
│   │   ├── models/    # Pydantic schemas
│   │   └── utils/     # Helpers
│   └── requirements.txt
├── frontend/          # Next.js frontend
├── data/              # Cloned repos & indexes
├── eval/              # Evaluation scripts
└── README.md
```

## Deployment

### Backend (Render / Railway)
The backend is prepared for deployment on Render or Railway. 

1. Connect your GitHub repository.
2. Set the root directory if necessary (default is project root).
3. The `Procfile` will automatically handle the start command.
4. Set Environment Variables:
    - `GEMINI_API_KEY`
    - `PYTHON_VERSION`: 3.11.0
    - `PORT`: 8000

### Frontend (Vercel)
The frontend is already configured for Vercel.

1. Connect the `frontend/` directory to a new Vercel project.
2. Configure **Rewrites**: Ensure `/api/:path*` points to your **production backend URL**.
3. Redeploy.

## License

MIT

