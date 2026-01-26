# 🚀 RepoPilot AI

<div align="center">

![RepoPilot Banner](https://img.shields.io/badge/RepoPilot-Engineering_Tool-6366f1?style=for-the-badge&logo=github)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14+-000000?style=flat-square&logo=next.js&logoColor=white)
![LLM Support](https://img.shields.io/badge/LLM-Groq_%2F_OpenAI-f55036?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

**A retrieval-augmented engineering tool that maps your repository, understands context, and helps you ship faster.**

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [Deployment](#-deployment)

</div>

---

## 💡 Core Principle

> **"Grounded-first, generate-second."**

Unlike generic chat tools, RepoPilot AI**indexes your actual codebase**. All answers are grounded in repository evidence (file citations). If evidence is missing, it refuses to hallucinate.

## ✨ Features

- 🔍 **Smart Ingestion**: Clone & analyze any GitHub repo or local path.
- ⚡ **Groq-Powered Speed**: Uses **Llama 3 70B** on Groq for sub-second reasoning.
- 🧩 **Evidence-Based Q&A**: Every answer cites specific files and line numbers.
- 🛠️ **Code Generation**: Generates context-aware diffs and unit tests.
- 🛡️ **Safe Fallback**: Validates inputs and refuses vague/unsafe requests.

## 🏗️ Architecture

- **Backend**: FastAPI (Python) with `chromadb` (Vector Store) and `langchain`.
- **Frontend**: Next.js 14 (TypeScript) with Tailwind CSS.
- **AI Engine**: Groq API (Llama 3) + Mock Embeddings (Hybrid retrieval).
- **Deployment**: Optimized for Railway (Monorepo support).

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Groq API Key](https://console.groq.com) (Free)

### 1. Setup
```bash
# Clone
git clone <repo-url>
cd repopilot

# Setup Virtual Environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install Backend Deps
pip install -r backend/requirements.txt

# Configure Environment
cp .env.example .env
# Edit .env: Add your OPENAI_API_KEY (Groq Key)
```

### 2. Run Locally
**Backend** (Port 8001)
```bash
./backend/run_backend.bat  # Windows
# or manually: uvicorn app.main:app --port 8001
```

**Frontend** (Port 3000)
```bash
cd frontend
npm install
npm run dev
```

Visit [`http://localhost:3000`](http://localhost:3000) to start chatting with your repos!

## 🌍 Deployment

🚀 **Production Ready for Railway**

This project is configured as a **Monorepo**.
For detailed deployment instructions, please read **[DEPLOYMENT.md](./DEPLOYMENT.md)**.

**Quick Specs:**
*   **Service 1 (Backend)**: Python / FastAPI
*   **Service 2 (Frontend)**: Node.js / Next.js
*   **Env Vars**: `OPENAI_API_KEY` (Groq), `OPENAI_BASE_URL` (https://api.groq.com/openai/v1)

## 📂 Project Structure

```
repopilot/
├── backend/           # 🧠 FastAPI Core
│   ├── app/           # Logic, Routes, Utils
│   └── Dockerfile     # Python runtime
├── frontend/          # 🎨 Next.js UI
│   ├── src/           # Components & Pages
│   └── Dockerfile     # Node runtime
├── data/              # 🗄️ Local Vector Store
├── scripts/           # 🛠️ Verification Utilities
└── railway.json       # 🚂 Deployment Config
```

## 📜 License

MIT © RepoPilot Team
