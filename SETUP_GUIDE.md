# 🚀 RepoPilot VS Code Extension - Setup Guide

A complete guide to running the RepoPilot VS Code extension locally.

---

## 📋 Prerequisites

- ✅ **Python 3.11+**
- ✅ **Node.js 18+** and npm
- ✅ **VS Code**
- ✅ **Git**

---

## ⚡ Quick Start

### Terminal 1: Start Backend

```powershell
cd "c:\Users\mohit\Desktop\visual studio\repopilot\backend"
.\venv\Scripts\Activate.ps1
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8001 --reload
```

**Expected output:**
```
starting_repopilot version=0.1.0 embedding_provider=Gemini chat_provider=Groq
INFO: Uvicorn running on http://127.0.0.1:8001
```

### Terminal 2: Run Extension

```powershell
cd "c:\Users\mohit\Desktop\visual studio\repopilot\vscode-extension"
npm install  # Only first time
npm run compile
code .
```

Then press **F5** in VS Code to launch the Extension Development Host.

---

## 🔧 Detailed Setup

### Step 1: Backend Setup

1. **Navigate to backend:**
   ```powershell
   cd "c:\Users\mohit\Desktop\visual studio\repopilot\backend"
   ```

2. **Create virtual environment** (first time only):
   ```powershell
   python -m venv venv
   ```

3. **Activate and install dependencies:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. **Verify `.env` file exists** at project root with:
   ```env
   GEMINI_API_KEY=...       # For embeddings
   OPENAI_API_KEY=...       # For chat (Groq)
   OPENAI_BASE_URL=https://api.groq.com/openai/v1
   ```

5. **Start backend:**
   ```powershell
   .\venv\Scripts\python.exe -m uvicorn app.main:app --port 8001 --reload
   ```

### Step 2: Extension Setup

1. **Open new terminal** (keep backend running)

2. **Navigate to extension:**
   ```powershell
   cd "c:\Users\mohit\Desktop\visual studio\repopilot\vscode-extension"
   ```

3. **Install dependencies:**
   ```powershell
   npm install
   ```

4. **Compile extension:**
   ```powershell
   npm run compile
   ```

5. **Open in VS Code:**
   ```powershell
   code .
   ```

6. **Press F5** to launch Extension Development Host

### Step 3: Test the Extension

In the Extension Development Host window:

1. **File → Open Folder** → Select any code repository
2. Look for **RepoPilot icon** in the sidebar
3. Wait for **auto-indexing** to complete
4. **Ask a question** in the chat!

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  VS Code Extension (TypeScript)                         │
│  - Chat UI, Commands, Auto-indexing                     │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP (localhost:8001)
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Backend Server (FastAPI)                               │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Embeddings      │  │ Chat LLM        │              │
│  │ Provider:       │  │ Provider:       │              │
│  │ Gemini ✓        │  │ Groq ✓          │              │
│  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────────────────────────────┐           │
│  │ Vector Store: ChromaDB                  │           │
│  └─────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

**Provider Priority:**
- **Embeddings**: Gemini → OpenAI → Mock
- **Chat LLM**: Groq → Gemini → Mock

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| Backend won't start | `pip install -r requirements.txt` |
| Extension won't compile | `npm install && npm run compile` |
| "Connection refused" | Check backend is running on port 8001 |
| "Collection does not exist" | Restart backend (bug was fixed) |
| `/health` requests in logs | Normal! Extension health checks |

### Test Backend Health

```powershell
curl http://localhost:8001/health
```

Should return: `{"status":"healthy"}`

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `.env` | API keys (Gemini, Groq) |
| `backend/app/main.py` | Backend entry point |
| `vscode-extension/src/extension.ts` | Extension entry point |
| `vscode-extension/package.json` | Extension config |

---

## 🎯 VS Code Extension Features

- **Auto-indexing**: Automatically indexes workspace on open
- **Chat Panel**: Ask questions about your code
- **Code Actions**: Right-click → "Ask RepoPilot"
- **Code Lens**: Inline hints on functions
- **Status Bar**: Shows connection/indexing status

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+R` | Open RepoPilot Chat |
| `Ctrl+Shift+A` | Ask about selection |

### Commands (Ctrl+Shift+P)

- `RepoPilot: Open Chat`
- `RepoPilot: Index Workspace`
- `RepoPilot: Start Backend`
- `RepoPilot: Export Chat History`

---

## 🔑 Configuration

### VS Code Settings

```json
{
  "repopilot.backendUrl": "http://localhost:8001",
  "repopilot.autoIndexOnOpen": true
}
```

### Environment Variables (.env)

```env
# Server
PORT=8001
DEBUG=true

# Embeddings (Gemini - FREE)
GEMINI_API_KEY=your_key
GEMINI_EMBEDDING_MODEL=models/text-embedding-004

# Chat (Groq - FREE, fast)
OPENAI_API_KEY=your_groq_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_CHAT_MODEL=llama-3.3-70b-versatile
```

---

## 📞 Getting Help

1. Check backend terminal for error messages
2. Check VS Code Developer Tools (Help → Toggle Developer Tools)
3. Verify `.env` has correct API keys
4. Ensure only ONE backend is running

🚀 **Happy coding with RepoPilot!**
