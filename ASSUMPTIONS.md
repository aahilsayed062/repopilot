# 📋 RepoPilot AI - Assumptions & Constraints

> This document lists all assumptions made about repositories and the system's known limitations.

---

## 🏗️ Repository Assumptions

### Supported Languages & File Types

| Category | Extensions | Notes |
|----------|------------|-------|
| **Python** | `.py` | Full support |
| **JavaScript/TypeScript** | `.js`, `.ts`, `.jsx`, `.tsx` | Full support |
| **Web** | `.html`, `.css`, `.scss`, `.vue`, `.svelte` | Full support |
| **Java/Kotlin** | `.java`, `.kt` | Full support |
| **Go/Rust** | `.go`, `.rs` | Full support |
| **C/C++** | `.c`, `.cpp`, `.h`, `.hpp` | Full support |
| **Config** | `.json`, `.yaml`, `.yml`, `.toml` | Full support |
| **Docs** | `.md`, `.rst`, `.txt` | Full support |

### Size Limits

| Limit | Value | Reason |
|-------|-------|--------|
| Max repository size | 50 MB | Prevents excessive API usage |
| Max file count | 500 files | Embedding cost control |
| Max file size | 1 MB | Single file limit |
| Excluded: `node_modules/` | Always | Too large, not useful |
| Excluded: `.git/` | Always | Binary data |
| Excluded: `venv/`, `__pycache__/` | Always | Generated content |

### Repository Structure Expectations

1. **Source code in standard locations**: `src/`, `lib/`, `app/`, or root
2. **README.md present**: Used for understanding project context
3. **Package files**: `package.json`, `requirements.txt`, `pyproject.toml` for dependencies
4. **English comments/docs**: Model performance may degrade with non-English content

---

## 🔧 Build & Test Instructions

### Backend Requirements

```bash
# Required
Python 3.11+
pip (Python package manager)

# Setup
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux
pip install -r requirements.txt

# Run
uvicorn app.main:app --port 8000 --reload
```

### Extension Requirements

```bash
# Required
Node.js 18+
npm

# Setup
cd vscode-extension
npm install
npm run compile

# Run
Press F5 in VS Code
```

### Environment Variables

```bash
# .env file (copy from .env.example)
GEMINI_API_KEY=your_key_here   # Required for embeddings
GROQ_API_KEY=your_key_here     # Required for chat
MOCK_MODE=false                 # Set true for offline testing
```

---

## ⚠️ Known Limitations

### Embedding Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| 768-dimension vectors | May miss subtle semantic differences | Use top-8 retrieval |
| 2048 token context per chunk | Long functions split across chunks | Overlap strategy |
| English-optimized | Non-English code comments may not embed well | None currently |

### LLM Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Context window: 8K tokens | Large answers may be truncated | Chunking strategy |
| Knowledge cutoff | May not know latest frameworks | Rely on repo context |
| Rate limits (Groq free tier) | 30 requests/minute | Queue management |

### RAG Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Semantic search only | May miss exact keyword matches | Could add hybrid search |
| No cross-file reasoning | Can't follow complex imports | Return multiple chunks |
| No runtime analysis | Can't execute code | Round 1 constraint |

---

## 🎯 Grounding Strategy

### How We Ensure Grounded Responses

1. **Citations Required**: Every answer must include file paths and line numbers
2. **Confidence Scoring**: Low/Medium/High based on evidence quality
3. **Safe Refusal**: If no relevant context found, explicitly state it
4. **No Hallucination**: System prompt forbids making up file names or code

### Evidence Threshold

| Confidence | Criteria |
|------------|----------|
| **High** | 3+ relevant chunks found, direct match to query |
| **Medium** | 1-2 relevant chunks, partial match |
| **Low** | No chunks found, answering from general knowledge |

---

## 🚫 What We Do NOT Support (Round 1)

| Feature | Status | Round 2? |
|---------|--------|----------|
| Code execution | ❌ Not supported | Planned |
| Test execution | ❌ Not supported | Planned |
| Multi-repo analysis | ❌ Not supported | Maybe |
| Real-time file watching | ❌ Not supported | Planned |
| Branch comparison | ❌ Not supported | Maybe |
| Private repo auth | ❌ Not supported | Planned |

---

## 📊 Token Usage Estimates

| Operation | Gemini Tokens | Groq Tokens | Cost |
|-----------|---------------|-------------|------|
| Index 100-file repo | ~100K-150K | 0 | FREE |
| Single question | ~50 | ~2,000-4,000 | FREE |
| Code generation | ~50 | ~4,000-6,000 | FREE |

### Free Tier Capacity

- **Gemini**: 1,500 requests/minute → Can index ~15 repos/minute
- **Groq**: 14,400 requests/day → ~14,000 questions/day

---

## 🧪 Testing Assumptions

### Manual Testing Performed On

- [x] Python repositories (FastAPI, Flask)
- [x] JavaScript/React repositories
- [x] TypeScript repositories
- [ ] Java repositories (limited testing)
- [ ] Go repositories (limited testing)

### Edge Cases Considered

- [x] Empty repositories
- [x] Single-file repositories
- [x] Repositories with only documentation
- [x] Repositories near size limits
- [ ] Repositories with non-ASCII filenames

---

## 📝 Future Improvements

1. **Hybrid Search**: Combine semantic + keyword search
2. **Cross-file Reasoning**: Track imports and dependencies
3. **Code Execution**: Run tests in sandboxed environment (Round 2)
4. **Incremental Indexing**: Update only changed files
5. **Multi-language Support**: Better handling of non-English content

---

*Last Updated: 2026-01-28*  
*Document Version: 1.0*
