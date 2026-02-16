# 🎤 RepoPilot Demo Script — 5-Minute Hackathon Presentation

> **Target repo**: `demo_repo/` (TaskFlow API — 9 files, ~450 lines)
> **Backend port**: 8001 (check `.env`)
> **Time**: 5 minutes total

---

## 🔥 Flow 1: Setup & Index (45 seconds)

### What you say:
> "RepoPilot eliminates developer hallucinations. Let me show you — I'll load a project I've never seen before and ask questions about it."

### What you do:
1. Open VS Code with `demo_repo/` as workspace
2. Open RepoPilot sidebar panel
3. Click **📁 Index**
4. Wait for "✅ Repository indexed and ready!"

### Expected output:
```
✅ Repository demo_repo indexed and ready!
```

---

## 🔥 Flow 2: Grounded Q&A with Citations (60 seconds)

### Ask this EXACT question:
```
How does authentication work in this project?
```

### Expected highlights:
- Answer mentions JWT tokens, bcrypt password hashing, OAuth2PasswordBearer
- Citations point to `auth.py` with line ranges
- Confidence: **HIGH** (multiple source files match)
- Structured sections: Short Answer → Evidence From Code → Practical Next Step

### What you say:
> "Notice three things: every claim cites real code, it shows confidence level, and the answer has structured sections. This isn't ChatGPT guessing — it's grounded in YOUR code."

---

## 🔥 Flow 3: Smart Refusal — Hallucination Prevention (45 seconds)

### Ask this EXACT question:
```
Show me the Redis cache configuration
```

### Expected highlights:
- Answer says "no evidence found" / "not present in context"
- Confidence: **LOW**
- Zero or minimal citations
- No made-up file paths or code

### What you say:
> "This is our killer feature. When there's NO Redis anywhere in this codebase, RepoPilot refuses to make something up. Other AI tools would hallucinate fake Redis config files. We protect developers from false information."

---

## 🔥 Flow 4: Code Generation (60 seconds)

### Type this (use /generate prefix or click ⚡ Generate button):
```
Add logging to the authentication module
```

### Expected highlights:
- Plan with structured steps
- Diffs showing changes to `auth.py`
- Paste instructions for where to apply code
- `patterns_followed` showing it matched existing style

### What you say:
> "RepoPilot doesn't just generate code — it shows you WHERE to paste it, WHAT patterns it followed from your repo, and generates tests alongside the changes."

---

## 🔥 Flow 5: PyTest Generation (30 seconds)

### Click the 🧪 Tests button and use:
```
Generate tests for the authentication module
```

### Expected highlights:
- Generated pytest code covering `hash_password`, `verify_password`, `create_access_token`
- Test file name suggestion
- Coverage notes listing what's covered

### What you say:
> "One click — production-quality pytest cases generated from the actual code, not from some template."

---

## 🔥 Flow 6: Query Decomposition (30 seconds)

### Ask:
```
How would I add a notifications system to this project?
```

### Expected highlights:
- RepoPilot breaks this into sub-questions internally
- Answer covers multiple aspects: models, routes, config
- Practical next steps

### What you say:
> "Complex questions get decomposed into smaller sub-questions. RepoPilot thinks like an engineer, not just a search engine."

---

## 🎯 Closing (15 seconds)

> "RepoPilot is a repository-grounded assistant that never hallucinates. It uses RAG with semantic embeddings, hybrid search, and confidence scoring — all running on FREE Gemini and Groq APIs. Thank you."

---

## ⚠️ Emergency Backup Questions

If a demo fails, use these safe fallback questions:

| Question | Why it's safe |
|----------|---------------|
| "What database does this project use?" | Always returns SQLAlchemy/SQLite from `database.py` |
| "How are API routes organized?" | Returns clean answer from `routes.py` |
| "What is the project structure?" | Returns overview from `README.md` |
| "How is configuration managed?" | Returns answer from `config.py` |

---

## 🚫 DO NOT Ask These During Demo

| Bad Question | Why |
|-------------|-----|
| Anything about Terraform or Docker | Not in demo_repo, refusal might look awkward in demo |
| Very long multi-paragraph prompts | Response time may spike |
| Questions about specific line numbers | Too granular, boring for audience |
