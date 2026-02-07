# 🧠 RepoPilot AI - Complete Technical Explanation

> This document explains **every component, logic flow, and decision** in the RepoPilot system.

---

## 📋 Table of Contents

1. [System Overview](#-system-overview)
2. [Architecture Deep Dive](#-architecture-deep-dive)
3. [RAG Pipeline Explained](#-rag-pipeline-explained)
4. [Backend Services](#-backend-services)
5. [API Endpoints](#-api-endpoints)
6. [VS Code Extension](#-vs-code-extension)
7. [Data Flow Diagrams](#-data-flow-diagrams)
8. [LLM Integration](#-llm-integration)
9. [Vector Database (ChromaDB)](#-vector-database-chromadb)
10. [Token Economics](#-token-economics)

---

## 🎯 System Overview

### What is RepoPilot?

RepoPilot is a **RAG (Retrieval-Augmented Generation)** system that:
1. **Indexes** any GitHub repository or local codebase
2. **Answers questions** with citations to actual files
3. **Generates code** that follows existing patterns
4. **Creates tests** matching your repo's testing style

### Why RAG Instead of Sending All Code?

| Approach | Problem |
|----------|---------|
| Send ALL code to LLM | 100,000+ tokens = $5+ per question, slow, context limit |
| **RAG Approach** | Send only 5-10 relevant chunks = 3,000 tokens, fast, FREE |

**Key Insight**: For a question about "user authentication", you don't need the entire codebase. You only need the 5-10 files related to auth.

---

## 🏗️ Architecture Deep Dive

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER                                         │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    VS CODE EXTENSION                            ││
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐ ││
│  │  │  Chat UI   │ │  Commands  │ │  CodeLens  │ │  Formatter   │ ││
│  │  │  (Webview) │ │            │ │            │ │              │ ││
│  │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └──────┬───────┘ ││
│  │        └──────────────┴──────────────┴───────────────┘          ││
│  │                              │ HTTP API                          ││
│  └──────────────────────────────┼──────────────────────────────────┘│
│                                 ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    BACKEND (FastAPI)                            ││
│  │                                                                  ││
│  │  ┌─────────────────────── ROUTES ───────────────────────────┐  ││
│  │  │  /health  │  /repo/load  │  /repo/index  │  /chat/ask   │  ││
│  │  │           │              │               │  /chat/pytest │  ││
│  │  └───────────┴──────────────┴───────────────┴───────────────┘  ││
│  │                              │                                   ││
│  │  ┌─────────────────────── SERVICES ─────────────────────────┐  ││
│  │  │                                                           │  ││
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │  ││
│  │  │  │ RepoManager │  │   Chunker   │  │     Indexer     │   │  ││
│  │  │  │ (Git Clone) │  │ (Split Code)│  │ (Embed+Store)   │   │  ││
│  │  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │  ││
│  │  │         │                │                  │             │  ││
│  │  │  ┌──────▼──────┐  ┌──────▼──────┐  ┌───────▼─────────┐   │  ││
│  │  │  │  Retriever  │  │   Planner   │  │    Answerer     │   │  ││
│  │  │  │ (Semantic   │  │ (Query      │  │ (RAG Answer     │   │  ││
│  │  │  │  Search)    │  │  Decompose) │  │  Generation)    │   │  ││
│  │  │  └─────────────┘  └─────────────┘  └─────────────────┘   │  ││
│  │  │                                                           │  ││
│  │  │  ┌─────────────┐  ┌─────────────────────────────────┐    │  ││
│  │  │  │  Generator  │  │        TestGenerator            │    │  ││
│  │  │  │ (Code Gen)  │  │        (PyTest Gen)             │    │  ││
│  │  │  └─────────────┘  └─────────────────────────────────┘    │  ││
│  │  └───────────────────────────────────────────────────────────┘  ││
│  │                              │                                   ││
│  │  ┌─────────────────────── UTILS ────────────────────────────┐  ││
│  │  │  embeddings.py (Gemini)  │  llm.py (Groq)  │  logger.py  │  ││
│  │  └──────────────────────────────────────────────────────────┘  ││
│  └──────────────────────────────┼──────────────────────────────────┘│
│                                 │                                    │
│  ┌──────────────────────────────▼──────────────────────────────────┐│
│  │                    EXTERNAL SERVICES                             ││
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐││
│  │  │ Gemini API     │  │ Groq API       │  │ ChromaDB (Local)   │││
│  │  │ (Embeddings)   │  │ (Chat LLM)     │  │ (Vector Storage)   │││
│  │  │ FREE           │  │ FREE           │  │ FREE               │││
│  │  └────────────────┘  └────────────────┘  └────────────────────┘││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 RAG Pipeline Explained

### What is RAG?

**RAG = Retrieval-Augmented Generation**

Instead of having the LLM memorize all your code, we:
1. **Retrieve** relevant code snippets based on the question
2. **Augment** the LLM's context with those snippets
3. **Generate** an answer grounded in real code

### The RAG Process (Step by Step)

```
INDEXING PHASE (One-time)
═════════════════════════

Step 1: Clone Repository
┌──────────────────┐     ┌──────────────────┐
│ GitHub URL       │────▶│ Local Clone      │
│ or Local Path    │     │ /data/repo/abc   │
└──────────────────┘     └──────────────────┘

Step 2: Read & Filter Files
┌──────────────────┐     ┌──────────────────┐
│ All Files (100+) │────▶│ Code Files (73)  │
│                  │     │ Excludes:        │
│                  │     │ - node_modules   │
│                  │     │ - .git           │
│                  │     │ - images/binaries│
└──────────────────┘     └──────────────────┘

Step 3: Chunk Files
┌──────────────────┐     ┌──────────────────┐
│ Large Files      │────▶│ Chunks (~500     │
│ (thousands of    │     │ tokens each)     │
│ lines)           │     │ 123 chunks total │
└──────────────────┘     └──────────────────┘

Step 4: Embed Chunks
┌──────────────────┐     ┌──────────────────┐
│ Text Chunks      │────▶│ Vector Embeddings│
│ "def calculate"  │     │ [0.23, -0.45, ...│
│                  │     │ 768 dimensions   │
│  Gemini API      │     │                  │
└──────────────────┘     └──────────────────┘

Step 5: Store in ChromaDB
┌──────────────────┐     ┌──────────────────┐
│ Vectors +        │────▶│ ChromaDB         │
│ Metadata +       │     │ (Persistent)     │
│ Content          │     │ /data/repo/index │
└──────────────────┘     └──────────────────┘


QUERY PHASE (Every Question)
════════════════════════════

Step 1: User Asks Question
┌──────────────────┐
│ "How does auth   │
│  work in this    │
│  project?"       │
└────────┬─────────┘
         │
         ▼
Step 2: Query Decomposition (Planner)
┌──────────────────┐
│ Sub-queries:     │
│ 1. "auth login"  │
│ 2. "JWT token"   │
│ 3. "middleware"  │
└────────┬─────────┘
         │
         ▼
Step 3: Embed Question
┌──────────────────┐     ┌──────────────────┐
│ "auth login..."  │────▶│ [0.12, 0.88, ...]│
│                  │     │ 768 dimensions   │
│  Gemini API      │     │                  │
└──────────────────┘     └────────┬─────────┘
                                  │
                                  ▼
Step 4: Semantic Search (Retriever)
┌──────────────────┐     ┌──────────────────┐
│ Query Vector     │────▶│ Top 8 Similar    │
│                  │     │ Chunks Found     │
│  ChromaDB        │     │ (cosine distance)│
└──────────────────┘     └────────┬─────────┘
                                  │
                                  ▼
Step 5: Generate Answer (Answerer)
┌──────────────────┐     ┌──────────────────┐
│ Question +       │────▶│ Grounded Answer  │
│ 8 Code Chunks    │     │ with Citations   │
│                  │     │                  │
│  Groq LLM        │     │  File: auth.py   │
│                  │     │  Lines: 45-67    │
└──────────────────┘     └──────────────────┘
```

---

## 🔧 Backend Services

### 1. RepoManager (`repo_manager.py`)

**Purpose**: Handle repository operations (clone, scan, read files)

```python
# Key Methods:
load_repo(url)           # Clone from GitHub or load local path
list_files(repo_id)      # Return all eligible files
get_file_content(...)    # Read a specific file
```

**File Filtering Logic**:
```python
INCLUDED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",   # Code
    ".json", ".yaml", ".yml",               # Config
    ".md", ".rst", ".txt",                  # Docs
}

EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__",  # Not useful
    "venv", "dist", "build",                # Generated
}
```

---

### 2. Chunker (`chunker.py`)

**Purpose**: Split files into semantic chunks suitable for embedding

**Chunking Strategy**:
```
┌─────────────────────────────────────┐
│ Original File (2000 lines)          │
├─────────────────────────────────────┤
│ def function_1():     │ CHUNK 1     │
│     ...               │ ~500 tokens │
│     ...               │             │
├───────────────────────┼─────────────┤
│ (50 token overlap)    │             │
├───────────────────────┼─────────────┤
│ def function_2():     │ CHUNK 2     │
│     ...               │ ~500 tokens │
│     ...               │             │
├───────────────────────┼─────────────┤
│ (50 token overlap)    │             │
├───────────────────────┼─────────────┤
│ class MyClass:        │ CHUNK 3     │
│     ...               │ ~500 tokens │
└─────────────────────────────────────┘
```

**Key Parameters**:
- `CHUNK_SIZE = 500` tokens (~400 words)
- `OVERLAP = 50` tokens (context continuity)
- `MAX_CHUNKS_PER_FILE = 50` (prevent huge files)

**Semantic Awareness**:
```python
# Tries to break at natural boundaries:
NATURAL_BOUNDARIES = [
    "\nclass ",      # Class definitions
    "\ndef ",        # Function definitions
    "\nasync def ",  # Async functions
    "\n\n",          # Double newlines
]
```

---

### 3. Indexer (`indexer.py`)

**Purpose**: Orchestrate the indexing pipeline

```python
async def index_repo(repo_id):
    # 1. Get repo files
    files = await repo_manager.list_files(repo_id)
    
    # 2. Read file contents
    file_contents = {}
    for file in files:
        file_contents[path] = await repo_manager.get_file_content(...)
    
    # 3. Chunk all files
    chunks, stats = await chunker.chunk_repository(repo_id, file_contents)
    
    # 4. Embed chunks in batches
    for batch in chunks[::100]:  # Batches of 100
        embeddings = await embedding_service.embed_batch(texts)
        collection.add(embeddings, documents, metadatas)
    
    return {"indexed": True, "chunk_count": len(chunks)}
```

**ChromaDB Storage**:
```python
# Each chunk stored with:
{
    "id": "chunk_abc123",
    "embedding": [0.23, -0.45, ...],  # 768 dims
    "document": "def calculate_total...",
    "metadata": {
        "repo_id": "repo_xyz",
        "file_path": "src/utils.py",
        "start_line": 45,
        "end_line": 89,
        "language": "python",
        "chunk_type": "function",
        "token_count": 487
    }
}
```

---

### 4. Retriever (`retriever.py`)

**Purpose**: Semantic search over indexed chunks

```python
async def retrieve(repo_id, query, k=8):
    # 1. Embed the query
    query_vector = await embedding_service.embed_batch([query])
    
    # 2. Search ChromaDB
    results = collection.query(
        query_embeddings=query_vector,
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )
    
    # 3. Return chunks sorted by relevance
    return [Chunk(...) for result in results]
```

**Similarity Metric**: Cosine Similarity
```
similarity = cos(query_vector, chunk_vector)
           = (A · B) / (||A|| × ||B||)
           = value between -1 and 1
```

---

### 5. Planner (`planner.py`)

**Purpose**: Decompose complex queries into sub-queries (M7 requirement)

```python
DECOMPOSITION_PROMPT = """
Break this developer question into 2-4 specific sub-questions:
Question: {question}

Return JSON: {"sub_questions": ["q1", "q2", ...]}
"""

async def decompose(question):
    # Skip for simple questions
    if len(question.split()) < 10:
        return [question]
    
    # Ask LLM to decompose
    response = await llm.chat_completion(...)
    return response["sub_questions"]
```

**Example**:
```
Input:  "How does the authentication system work and where is the user data stored?"

Output: [
    "How does authentication/login work?",
    "Where is JWT token handling implemented?",
    "Where is user data stored in the database?"
]
```

---

### 6. Answerer (`answerer.py`)

**Purpose**: Generate grounded answers using RAG

```python
SYSTEM_PROMPT = """
You are RepoPilot. Answer questions using ONLY the provided code context.

Rules:
1. Cite files and line numbers
2. If no relevant context, say so
3. Return confidence level (high/medium/low)

Return JSON:
{
    "answer": "markdown text",
    "citations": [{"file_path": "...", "line_range": "L10-L20", ...}],
    "confidence": "high|medium|low",
    "assumptions": []
}
"""

async def answer(query, chunks):
    # Build context from chunks
    context = "\n---\n".join([
        f"File: {c.file_path}\nLines: {c.line_range}\n{c.content}"
        for c in chunks
    ])
    
    # Generate answer
    response = await llm.chat_completion([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
    ])
    
    return ChatResponse(**response)
```

---

### 7. Generator (`generator.py`)

**Purpose**: Generate code that follows repo patterns

```python
async def generate(repo_id, request):
    # 1. Retrieve relevant code patterns
    chunks = await retriever.retrieve(repo_id, request)
    
    # 2. Generate code following patterns
    response = await llm.chat_completion([
        {"role": "system", "content": CODE_GEN_PROMPT},
        {"role": "user", "content": f"Patterns:\n{context}\n\nRequest: {request}"}
    ])
    
    return GenerationResponse(
        plan="...",
        diffs=[...],
        tests="...",
        citations=[...]
    )
```

---

### 8. TestGenerator (`test_generator.py`)

**Purpose**: Generate PyTest test cases

```python
async def generate_tests(repo_id, target_file=None, target_function=None):
    # 1. Find source code
    code_chunks = await retriever.retrieve(repo_id, f"code in {target_file}")
    
    # 2. Find existing test patterns
    test_chunks = await retriever.retrieve(repo_id, "pytest test")
    
    # 3. Generate tests matching style
    response = await llm.chat_completion([
        {"role": "system", "content": PYTEST_PROMPT},
        {"role": "user", "content": f"Source:\n{code}\n\nExisting Tests:\n{tests}"}
    ])
    
    return {
        "tests": "import pytest\n\ndef test_...",
        "test_file_name": "test_utils.py",
        "explanation": "...",
        "coverage_notes": [...]
    }
```

---

## 🌐 API Endpoints

### Health Check
```
GET /health

Response: {
    "status": "healthy",
    "version": "1.0.0",
    "mock_mode": false
}
```

### Load Repository
```
POST /repo/load
Body: {
    "repo_url": "https://github.com/user/repo",
    "branch": "main"  // optional
}

Response: {
    "success": true,
    "repo_id": "abc123",
    "repo_name": "repo",
    "commit_hash": "def456",
    "stats": {"total_files": 73, ...}
}
```

### Index Repository
```
POST /repo/index
Body: {
    "repo_id": "abc123",
    "force": false  // re-index if true
}

Response: {
    "success": true,
    "indexed": true,
    "chunk_count": 123
}
```

### Ask Question
```
POST /chat/ask
Body: {
    "repo_id": "abc123",
    "question": "How does auth work?",
    "decompose": true
}

Response: {
    "answer": "Authentication is handled...",
    "citations": [
        {"file_path": "src/auth.py", "line_range": "L45-L67", ...}
    ],
    "confidence": "high",
    "assumptions": []
}
```

### Generate Code
```
POST /chat/generate
Body: {
    "repo_id": "abc123",
    "request": "Add a logout function"
}

Response: {
    "plan": "1. Add logout route...",
    "diffs": [{"file_path": "...", "diff": "..."}],
    "tests": "def test_logout()...",
    "citations": ["src/auth.py"]
}
```

### Generate PyTest
```
POST /chat/pytest
Body: {
    "repo_id": "abc123",
    "target_file": "src/utils.py",
    "target_function": "calculate_total"
}

Response: {
    "success": true,
    "tests": "import pytest\n\ndef test_calculate...",
    "test_file_name": "test_utils.py",
    "explanation": "Generated 5 test cases...",
    "coverage_notes": ["Covers edge cases", ...]
}
```

---

## 🖥️ VS Code Extension

### Structure
```
vscode-extension/
├── src/
│   ├── extension.ts        # Entry point, activation
│   ├── chatPanel.ts        # Main webview provider
│   ├── apiClient.ts        # HTTP client for backend
│   ├── types.ts            # TypeScript interfaces
│   ├── responseFormatter.ts # Format LLM output
│   ├── commands.ts         # VS Code commands
│   ├── statusBar.ts        # Status bar item
│   └── storage.ts          # Persist state
├── media/
│   ├── chat.html           # Webview HTML
│   ├── chat.css            # Webview styles
│   └── chat.js             # Webview JavaScript
└── package.json            # Extension manifest
```

### Extension ↔ Webview Communication

```
┌─────────────────────────────────────────┐
│           VS Code Extension             │
│  ┌───────────────────────────────────┐  │
│  │        chatPanel.ts               │  │
│  │                                   │  │
│  │  postMessage({type: 'STATUS'})────│──┼───┐
│  │                                   │  │   │
│  │  ◄────onMessage({type: 'ASK'})────│──┼───┤
│  │                                   │  │   │
│  └───────────────────────────────────┘  │   │
└─────────────────────────────────────────┘   │
                                              │
                   WebSocket-like             │
                                              │
┌─────────────────────────────────────────┐   │
│              Webview                    │   │
│  ┌───────────────────────────────────┐  │   │
│  │          chat.js                  │  │   │
│  │                                   │  │   │
│  │  ◄─────window.addEventListener────│──┼───┘
│  │        ('message', ...)           │  │
│  │                                   │  │
│  │  vscode.postMessage({type: 'ASK'})│──┼───►
│  │                                   │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 🤖 LLM Integration

### Gemini (Embeddings)

**File**: `utils/embeddings.py`

```python
class GeminiEmbeddings:
    MODEL = "models/text-embedding-004"
    DIMENSION = 768
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = genai.embed_content(
            model=self.MODEL,
            content=texts,
            task_type="retrieval_document"
        )
        return response['embedding']
```

**Why Gemini?**
- FREE (1,500 requests/minute)
- 768 dimensions (good balance of quality/speed)
- Fast response times

---

### Groq (Chat LLM)

**File**: `utils/llm.py`

```python
class GroqLLM:
    MODEL = "llama-3.3-70b-versatile"
    
    async def chat_completion(self, messages, json_mode=False):
        response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=messages,
            response_format={"type": "json_object"} if json_mode else None,
            temperature=0.1,  # Low for consistent code
            max_tokens=4096
        )
        return response.choices[0].message.content
```

**Why Groq?**
- FREE (14,400 requests/day)
- Llama-3.3-70B is excellent for code
- Fastest inference (~100ms latency)

---

## 💾 Vector Database (ChromaDB)

### What is ChromaDB?

ChromaDB is an **open-source vector database** that stores embeddings locally.

**Location**: `<repo_path>/index/` (inside each cloned repo)

### How It Works

```
┌──────────────────────────────────────────────────┐
│                    ChromaDB                       │
│  ┌────────────────────────────────────────────┐  │
│  │              Collection: repo_index         │  │
│  │  ┌────────┬───────────┬───────────────────┐│  │
│  │  │   ID   │ Embedding │     Metadata       ││  │
│  │  ├────────┼───────────┼───────────────────┤│  │
│  │  │chunk_1 │[0.23,...]│{file: "auth.py"...}││  │
│  │  │chunk_2 │[0.45,...]│{file: "utils.py"..}││  │
│  │  │chunk_3 │[-0.12,..]│{file: "main.py"...}││  │
│  │  │  ...   │   ...    │       ...          ││  │
│  │  └────────┴───────────┴───────────────────┘│  │
│  └────────────────────────────────────────────┘  │
│                                                   │
│  Index Type: HNSW (Hierarchical Navigable Small │
│              World) - O(log n) search            │
│  Distance: Cosine Similarity                     │
└──────────────────────────────────────────────────┘
```

### Query Process

```python
# Input: Query vector [0.34, -0.12, ...]
# Output: Top 8 most similar chunks

results = collection.query(
    query_embeddings=[[0.34, -0.12, ...]],
    n_results=8,
    include=["documents", "metadatas", "distances"]
)

# Returns sorted by cosine similarity:
# chunk_45 (similarity: 0.92)
# chunk_12 (similarity: 0.87)
# chunk_78 (similarity: 0.85)
# ...
```

---

## 💰 Token Economics

### Where Tokens Are Used

| Operation | Gemini (Embeddings) | Groq (Chat) | Cost |
|-----------|---------------------|-------------|------|
| Index 1 chunk | ~500 tokens input | 0 | FREE |
| Index 100 files | ~50,000 tokens | 0 | FREE |
| 1 Question | ~50 tokens | ~3,000 | FREE |
| 1 Code Generation | ~50 tokens | ~5,000 | FREE |
| 1 PyTest Generation | ~50 tokens | ~4,000 | FREE |

### Free Tier Limits

| Service | Limit | Typical Usage | Capacity |
|---------|-------|---------------|----------|
| Gemini | 1,500 req/min | 1-2 req/question | 750x headroom |
| Groq | 30 req/min | 1 req/question | 30x headroom |
| Groq | 14,400 req/day | 50 req/day | 288x headroom |

### Cost Comparison

| Scenario | With OpenAI | With RepoPilot (Gemini+Groq) |
|----------|-------------|------------------------------|
| Index 100 files | $5-10 (GPT-4) | $0 |
| 100 Questions/day | $20-50 | $0 |
| 1 Month usage | $500+ | $0 |

---

## 🔐 Security Considerations

1. **API Keys**: Stored in `.env` (gitignored)
2. **Local Data**: All indexed data stays local
3. **No Cloud Storage**: ChromaDB runs locally
4. **No Telemetry**: No data sent to external services except LLM APIs

---

## 🧪 Testing the System

### Manual Testing Checklist

1. **Health Check**: `GET http://localhost:8000/health`
2. **Load Repo**: Submit a GitHub URL
3. **Index**: Click "Index" button
4. **Ask Question**: "What does this project do?"
5. **Check Citations**: Verify file paths are real
6. **Generate Code**: "Add a new utility function"
7. **Generate Tests**: "Create tests for utils.py"

---

## 📝 Summary

RepoPilot is a complete **RAG-based code assistant** that:

1. **Indexes** repositories by chunking and embedding code
2. **Searches** semantically using vector similarity
3. **Answers** questions with grounded citations
4. **Generates** code following existing patterns
5. **Creates tests** matching your testing style

All using **FREE APIs** (Gemini + Groq) with **local storage** (ChromaDB).

---

*Last Updated: 2026-01-28*  
*Document Length: ~600 lines*
