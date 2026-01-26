# RepoPilot AI - Design Document

## Overview
RepoPilot AI is a **repository-grounded engineering assistant** that ingests codebases and provides grounded Q&A, query decomposition, and code generation.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend  │────▶│   FastAPI    │────▶│  ChromaDB   │
│  (Next.js)  │     │   Backend    │     │ Vector Store│
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌──────────┐  ┌──────────┐
              │   LLM    │  │ Planner  │
              │ (Groq)   │  │ (Decomp) │
              └──────────┘  └──────────┘
```

## Agents / Services

| Service | File | Purpose |
|---------|------|---------|
| **Indexer** | `indexer.py` | Ingests repo, chunks files, stores embeddings |
| **Retriever** | `retriever.py` | Semantic search over indexed chunks |
| **Planner** | `planner.py` | Query decomposition for complex questions |
| **Answerer** | `answerer.py` | Grounded Q&A with citations |
| **Generator** | `generator.py` | Code generation with diffs and tests |

## Data Flow

### 1. Ingestion Flow
```
User submits repo URL
        ↓
RepoManager clones/validates
        ↓
Chunker splits into code/doc chunks
        ↓
EmbeddingService generates vectors
        ↓
Indexer stores in ChromaDB
```

### 2. Q&A Flow
```
User asks question
        ↓
Planner decomposes (if complex)
        ↓
Retriever fetches top-k chunks
        ↓
Answerer generates grounded response
        ↓
Response includes citations + confidence
```

### 3. Generation Flow
```
User requests code change
        ↓
Retriever fetches relevant context
        ↓
Generator creates plan + diffs + tests
        ↓
User reviews before applying
```

## Grounding Strategy

1. **Context-Only Answers**: LLM is instructed to use ONLY provided chunks.
2. **Mandatory Citations**: Every claim must cite file + line range.
3. **Confidence Levels**: `high` (grounded), `medium` (partial), `low` (general knowledge).
4. **Safe Refusal**: If no context, explicitly state uncertainty.
5. **No Auto-Execution**: Code generation produces diffs, not direct file writes.

## Technology Stack
- **Backend**: FastAPI, ChromaDB, Pydantic
- **Frontend**: Next.js 14, TypeScript
- **LLM**: Groq (Llama 3.3 70B) via OpenAI-compatible API
- **Embeddings**: Mock (random) for free tier; supports OpenAI/Gemini
