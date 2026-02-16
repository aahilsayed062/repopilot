# RepoPilot Website — Standalone Web App

A **separate, deployable website** that lives in `repopilot/website/` — completely independent from the VS Code extension. Users paste a GitHub URL, the backend clones & analyzes the repo using Gemini API, and the frontend renders an interactive architecture overview with a codebase structure graph.

> **IMPORTANT:** This is **100% separate** from the VS Code extension codebase. We are NOT touching `vscode-extension/`, the existing `backend/`, or the existing `frontend/` at all.

---

## 🎯 Core Concept

| Step | What Happens |
|------|-------------|
| 1 | User pastes a GitHub repo URL on the website |
| 2 | Backend clones the repo (shallow, minimal), scans file tree |
| 3 | Backend builds a **file/folder structure map** with language detection |
| 4 | LLM (Gemini Flash) analyzes the structure + key files → produces **architecture summary** |
| 5 | Frontend renders an **interactive codebase graph** + architecture explanation |

---

## 📁 Directory Structure: `repopilot/website/`

```
repopilot/
├── website/                    ← ALL website code lives here
│   ├── frontend/               ← Next.js + Tailwind (copied from existing frontend as base)
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── page.tsx              (Landing — URL input)
│   │   │   │   ├── analyze/
│   │   │   │   │   └── page.tsx          (Analysis dashboard)
│   │   │   │   ├── globals.css
│   │   │   │   └── layout.tsx
│   │   │   ├── components/
│   │   │   │   ├── landing/              (Existing landing components)
│   │   │   │   ├── ui/                   (Existing UI effects — Silk, Shuffle, etc.)
│   │   │   │   ├── UrlInput.tsx          (GitHub URL input bar)
│   │   │   │   ├── ArchitectureCard.tsx  (Architecture summary panel)
│   │   │   │   ├── CodebaseGraph.tsx     (Interactive tree/graph viz)
│   │   │   │   ├── TechStackBadges.tsx   (Detected languages/frameworks)
│   │   │   │   ├── FileExplorer.tsx      (Collapsible file tree)
│   │   │   │   ├── StatsPanel.tsx        (Repo stats: files, lines, etc.)
│   │   │   │   └── LoadingState.tsx      (Skeleton + progress animation)
│   │   │   └── lib/
│   │   │       └── api.ts               (Backend API client)
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   └── backend/                ← FastAPI (lightweight, API-key driven)
│       ├── app/
│       │   ├── main.py                   (FastAPI entry)
│       │   ├── config.py                 (Settings: GEMINI_API_KEY, etc.)
│       │   ├── routes/
│       │   │   ├── analyze.py            (POST /analyze — main endpoint)
│       │   │   └── health.py             (GET /health)
│       │   └── services/
│       │       ├── repo_fetcher.py       (Clone + scan GitHub repos)
│       │       ├── structure_analyzer.py (Build file tree + language stats)
│       │       ├── architecture_llm.py   (Gemini Flash architecture analysis)
│       │       └── graph_builder.py      (Generate graph data for frontend)
│       ├── requirements.txt
│       └── .env.example
```

---

## 🔧 Tech Stack Decisions

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Frontend** | Next.js 14 + Tailwind v4 | Same as existing frontend, keeps skills consistent |
| **Backend** | FastAPI (Python) | Same framework, but fresh lightweight instance |
| **LLM** | Gemini 2.0 Flash (Google AI) | Free tier: 15 RPM / 1M tokens/min — great for analysis |
| **Embeddings** | NOT needed for MVP | We're doing structural analysis, not RAG search |
| **Graph Viz** | D3.js or React Flow | Interactive, zoomable codebase structure graph |
| **Deployment** | Vercel (frontend) + Railway/Render (backend) | Free tiers available for both |

> **Why Gemini Flash?** — 2.0 Flash has a **1M token context window** in the free tier, which is perfect for sending large file trees + key file contents in a single call. No embeddings/vector DB needed for the MVP, keeping costs at $0.

---

## 🚀 Feature Breakdown

### Phase 1 — Core MVP (What We Build First)

#### 1. GitHub URL → Repo Fetch
- Accept any public GitHub URL (e.g., `https://github.com/user/repo`)
- Shallow clone (`--depth 1`) to minimize bandwidth
- Auto-detect default branch
- Timeout protection (60s max)
- Cleanup cloned repos after analysis (temp directory)

#### 2. Codebase Structure Analysis (Zero LLM Tokens)
- Walk the file tree, classify every file by language (Python, JS, TS, etc.)
- Compute stats: total files, lines of code per language, directory depth
- Detect common patterns: `src/`, `tests/`, `docs/`, `config/`, monorepo structure
- Identify key files: `README.md`, `package.json`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `Makefile`, `.env.example`
- Build a **JSON tree structure** for the graph

#### 3. LLM Architecture Explanation (Gemini Flash)
- Send the file tree + contents of key config files (package.json, requirements.txt, Dockerfile, etc.) to Gemini
- Prompt asks for:
  - **One-liner summary** of what the project does
  - **Tech stack** (languages, frameworks, databases, infra)
  - **Architecture pattern** (monolith, microservices, monorepo, etc.)
  - **Key components** and what each does
  - **Entry points** (main files, API routes, etc.)
  - **How data flows** through the system
- Return structured JSON response

#### 4. Interactive Codebase Graph
- **Zoomable tree visualization** of the file structure using D3.js or React Flow
- Color-coded by language/file type
- Collapsible directories
- Click a node → see file details (size, language, role)
- Highlight key files (entry points, configs)

#### 5. Frontend Dashboard
- **Landing page**: Stunning URL input with animated background
- **Analysis page**: Split view —
  - Left: Architecture summary (rendered markdown)
  - Right: Interactive codebase graph
  - Bottom: Stats bar (files, languages, lines of code)

---

### Phase 2 — Enhancements (Make It Impressive)

#### 6. Dependency Graph
- Parse `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`
- Show a **dependency network graph** — which packages the project uses
- Group by category: framework, testing, database, devtools, etc.

#### 7. README Analysis & Summary
- If README exists, send to Gemini for a **TL;DR summary**
- Extract: purpose, installation steps, key features, badges

#### 8. Architecture Diagram (Auto-Generated)
- Generate a **Mermaid.js diagram** from the LLM analysis
- Show component relationships, data flow, API boundaries
- Render inline on the dashboard

#### 9. Code Complexity Heatmap
- Color-code the file tree by file size / estimated complexity
- Larger/more complex files glow warmer (orange → red)
- Simple files stay cool (green → blue)

#### 10. Smart File Preview
- Click any file in the graph → show syntax-highlighted preview
- For key files (main entry, config, routes) → auto-summarize using LLM

#### 11. Shareable Analysis Links
- After analysis, generate a unique URL (e.g., `/analyze/abc123`)
- Cache results for 24h so others can view without re-analyzing
- Social share meta tags (OpenGraph) for Twitter/LinkedIn preview

#### 12. Compare Repos
- Side-by-side analysis of two repos
- Show differences in tech stack, structure, complexity

---

## 🔑 API Design

### `POST /api/analyze`

**Request:**
```json
{
  "github_url": "https://github.com/user/repo",
  "branch": "main"
}
```

**Response:**
```json
{
  "repo_name": "user/repo",
  "summary": "A Next.js full-stack web application for...",
  "tech_stack": ["Next.js", "TypeScript", "Tailwind", "PostgreSQL"],
  "architecture_pattern": "Monolith (Full-Stack Next.js)",
  "components": [
    {
      "name": "API Routes",
      "path": "src/app/api/",
      "description": "RESTful API endpoints for..."
    }
  ],
  "entry_points": ["src/app/page.tsx", "src/app/api/route.ts"],
  "data_flow": "User → Next.js Page → API Route → PostgreSQL → Response",
  "stats": {
    "total_files": 142,
    "total_lines": 18340,
    "languages": {"TypeScript": 65, "CSS": 20, "JSON": 15},
    "directory_depth": 5
  },
  "file_tree": {},
  "dependency_graph": {},
  "mermaid_diagram": "graph TD\n  A[User] --> B[Frontend]..."
}
```

---

## ⚡ Token Optimization Strategy (Stay in Free Tier)

| Technique | How It Saves Tokens |
|-----------|-------------------|
| **Structural analysis first** | File tree building, language detection, stats = **zero tokens** |
| **Selective file reading** | Only send key files (README, package.json, main entry) to LLM, not entire repo |
| **Tree-as-text compression** | Send file tree as indented text (not full paths), ~500 tokens for 200-file repo |
| **Single-shot prompt** | One Gemini call with structured output, not multiple calls |
| **Response caching** | Cache results by repo+commit hash, avoid re-analyzing same repo |
| **Gemini Flash 2.0** | 15 RPM free, 1M token context = plenty for any repo |

**Estimated tokens per analysis:** ~2,000-5,000 input + ~1,000 output = well within free limits.

---

## 🎨 UI Vision

- **Dark theme** with gradient accents (deep navy → electric blue → purple)
- **Glassmorphism** cards for architecture summary and stats
- **Animated background** on landing page (reuse Silk/MetallicPaint effects from existing frontend)
- **Smooth transitions** between landing → analysis (page transition animations)
- **Graph should feel alive**: hover effects, smooth zoom, animated node connections
- **Mobile responsive**: graph simplifies to collapsible tree on mobile

---

## 🔐 Security & Deployment

| Concern | Solution |
|---------|----------|
| API key exposure | Backend-only — Gemini key in `.env`, never sent to frontend |
| Abuse protection | Rate limiting (10 analyses/hour per IP) |
| Large repos | Max 100MB shallow clone, timeout after 60s |
| Temp files | Auto-cleanup cloned repos after analysis |
| CORS | Allow only the deployed frontend domain |

---

## 🧑‍💻 How to Run

### Backend
```bash
cd repopilot/website/backend
pip install -r requirements.txt
cp .env.example .env   # Add your GEMINI_API_KEY
uvicorn app.main:app --reload --port 8001
```

### Frontend
```bash
cd repopilot/website/frontend
npm install
npm run dev   # runs on port 3000
```
