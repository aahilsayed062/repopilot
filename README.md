# 🤖 RepoPilot AI - Repository-Grounded Assistant

> **Problem Statement 2 (PS2)** - AlphaByte 3.0 | GDGC PCCE | Develop Design Innovate

A VS Code extension that uses **RAG (Retrieval-Augmented Generation)** to answer questions about any GitHub repository with grounded, citation-backed responses.

---

## ✨ Features

| Feature | Status | Description |
|---------|--------|-------------|
| **Repository-aware Q&A** | ✅ | Ask questions about code, get answers with file citations |
| **Query Decomposition** | ✅ | Complex questions are split into sub-queries |
| **Code Generation** | ✅ | Generate code that follows repo patterns |
| **Safe Refusal** | ✅ | Won't hallucinate - shows confidence levels |
| **Grounded Answers** | ✅ | All answers cite real files from the repo |

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- **Python 3.11+** ([Download](https://www.python.org/downloads/))
- **Node.js 18+** ([Download](https://nodejs.org/))
- **Git** ([Download](https://git-scm.com/downloads))
- **VS Code** ([Download](https://code.visualstudio.com/))

### Step 1: Clone & Setup Environment

```bash
git clone https://github.com/YOUR_USERNAME/repopilot.git
cd repopilot
```

### Step 2: Get Free API Keys

| Service | Get Key | Purpose |
|---------|---------|---------|
| **Gemini** | [ai.google.dev](https://ai.google.dev/) | Embeddings (FREE) |
| **Groq** | [console.groq.com](https://console.groq.com/) | Chat LLM (FREE) |

### Step 3: Configure Environment

Copy `.env.example` to `.env` and add your keys:

```bash
# Copy the example
copy .env.example .env

# Edit .env with your keys:
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
```

### Step 4: Start the Backend

**Windows:**
```bash
start_backend.bat
```

**Mac/Linux:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8001 --reload
```

You should see:
```
INFO: Uvicorn running on http://127.0.0.1:8001
embedding_provider=Gemini chat_provider=Groq
```

### Step 5: Run the Extension

1. Open `vscode-extension` folder in VS Code
2. Press **F5** to launch Extension Development Host
3. In the new VS Code window, click **RepoPilot** icon in sidebar
4. Click **📁 Index** and enter a GitHub URL
5. Start asking questions!

---

## 📁 Project Structure

```
repopilot/
├── backend/                    # Python FastAPI server
│   ├── app/
│   │   ├── main.py            # Entry point
│   │   ├── routes/            # API endpoints
│   │   │   ├── repo.py        # /repo/load, /repo/index
│   │   │   ├── chat.py        # /chat/ask, /chat/generate
│   │   │   └── health.py      # /health
│   │   ├── services/          # Business logic
│   │   │   ├── repo_manager.py  # Git operations
│   │   │   ├── chunker.py       # Code splitting
│   │   │   ├── indexer.py       # Vector storage
│   │   │   ├── retriever.py     # Semantic search
│   │   │   ├── answerer.py      # RAG answers
│   │   │   └── planner.py       # Query decomposition
│   │   └── utils/             # Embeddings, LLM, logging
│   └── requirements.txt
│
├── vscode-extension/          # TypeScript VS Code extension
│   ├── src/                   # Extension source
│   ├── media/                 # Webview UI
│   └── package.json
│
├── .env.example               # Environment template
├── start_backend.bat          # Windows launcher
├── README.md                  # This file
└── REPOPILOT_ASSESSMENT.md    # Full technical assessment
```

---

## 🔧 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Check backend status |
| `/repo/load` | POST | Clone/load a repository |
| `/repo/index` | POST | Index repository for RAG |
| `/chat/ask` | POST | Ask a question |
| `/chat/generate` | POST | Generate code |

---

## 🧠 How It Works

```
1. INDEX: Clone repo → Split into chunks → Embed with Gemini → Store in ChromaDB
2. QUERY: Embed question → Search similar chunks → Send to Groq LLM → Return answer
```

| Step | Tokens | Cost |
|------|--------|------|
| Index 100 files | ~150K | FREE (Gemini) |
| Ask 1 question | ~3K | FREE (Groq) |

---

## 🛠️ Development

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate    # Windows
pip install -r requirements.txt
uvicorn app.main:app --port 8001 --reload
```

### Extension

```bash
cd vscode-extension
npm install
npm run compile
# Press F5 in VS Code to launch
```

---

## 📝 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | For embeddings |
| `GROQ_API_KEY` | Yes | For chat completion |
| `OPENAI_API_KEY` | No | Alternative LLM provider |
| `MOCK_MODE` | No | Set `true` for testing without APIs |

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| "Cannot connect to backend" | Make sure backend is running on port 8001 |
| "No API key" | Check your `.env` file has valid keys |
| "Repository too large" | Max 50MB and 500 files by default |

---

## 📚 Documentation

- **[REPOPILOT_ASSESSMENT.md](./REPOPILOT_ASSESSMENT.md)** - Full technical assessment and requirements checklist

---

## 👥 Team

**AlphaByte 3.0** | GDGC PCCOE | Develop Design Innovate

---

## 📄 License

MIT License - See LICENSE file for details.
