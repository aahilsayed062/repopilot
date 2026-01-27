# 🚀 RepoPilot AI - VS Code Extension

<div align="center">

![RepoPilot Banner](https://img.shields.io/badge/RepoPilot-VS_Code_Extension-6366f1?style=for-the-badge&logo=visual-studio-code)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.3+-3178C6?style=flat-square&logo=typescript&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-Groq_%2F_Gemini-f55036?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

**A repository-grounded AI coding assistant for VS Code that refuses to hallucinate.**

</div>

---

## 💡 What is RepoPilot?

> **"Grounded-first, generate-second."**

RepoPilot is a VS Code extension that indexes your codebase and provides AI-powered answers grounded in YOUR actual code. Unlike generic AI assistants, every answer cites specific files and line numbers.

## ✨ Features

- 🔍 **Smart Indexing** - Automatically indexes your workspace
- ⚡ **Grounded Answers** - Every response cites real files
- 🛠️ **Code Generation** - Generate code matching your patterns
- 🧪 **Test Generation** - Auto-generate PyTest tests
- 🛡️ **Safe Refusals** - Refuses risky operations with explanations
- 📊 **Confidence Scores** - See how certain the AI is

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  VS Code Extension (TypeScript)                         │
│  ├─ Chat Panel (Sidebar)                                │
│  ├─ Commands & Code Actions                             │
│  └─ Auto-indexing                                       │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP (localhost:8001)
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Backend Server (FastAPI + Python)                      │
│  ├─ Embeddings: Gemini (FREE)                          │
│  ├─ Chat LLM: Groq (FREE, fast)                        │
│  └─ Vector Store: ChromaDB                             │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- VS Code

### 1. Start Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8001 --reload
```

### 2. Run Extension

```powershell
cd vscode-extension
npm install
npm run compile
code .
# Press F5 in VS Code
```

### 3. Configure API Keys

Create `.env` in project root:
```env
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_groq_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
```

## 📦 Project Structure

```
repopilot/
├── backend/              # FastAPI Backend
│   ├── app/
│   │   ├── routes/       # API endpoints
│   │   ├── services/     # Business logic
│   │   └── utils/        # LLM, embeddings
│   └── requirements.txt
├── vscode-extension/     # VS Code Extension
│   ├── src/              # TypeScript source
│   ├── media/            # Chat UI assets
│   └── package.json
├── .env                  # API keys (create this)
├── README.md
└── SETUP_GUIDE.md        # Detailed setup instructions
```

## 🎯 Usage

### Commands

| Command | Description |
|---------|-------------|
| `RepoPilot: Open Chat` | Open the chat panel |
| `RepoPilot: Index Workspace` | Re-index the current workspace |
| `RepoPilot: Ask About Selection` | Ask about selected code |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+R` | Open Chat |
| `Ctrl+Shift+A` | Ask about selection |

### Chat Commands

- **Ask questions**: Just type naturally
- **Generate code**: Prefix with `/generate`

## 🔑 API Keys

| Provider | Purpose | Get Key |
|----------|---------|---------|
| **Gemini** | Embeddings (FREE) | [aistudio.google.com](https://aistudio.google.com/apikey) |
| **Groq** | Chat LLM (FREE) | [console.groq.com](https://console.groq.com) |

## 📚 Documentation

- **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** - Detailed setup instructions
- **[roadmap.md](./roadmap.md)** - Complete feature roadmap

## 🔧 Development

### Build Extension
```powershell
cd vscode-extension
npm run compile    # Dev build
npm run package    # Production build
```

### Package for Distribution
```powershell
npm install -g @vscode/vsce
vsce package
# Creates: repopilot-1.0.0.vsix
```

## 📜 License

MIT © RepoPilot Team
