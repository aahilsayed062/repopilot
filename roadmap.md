# RepoPilot AI - Complete Hackathon Build Guide
## Problem Statement 2 (PS-2) Implementation

---

## 📋 TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Problem Understanding](#problem-understanding)
3. [System Architecture](#system-architecture)
4. [Core Components](#core-components)
5. [Implementation Roadmap](#implementation-roadmap)
6. [Technical Stack](#technical-stack)
7. [Feature Details](#feature-details)
8. [Demo Strategy](#demo-strategy)
9. [Judging Criteria Alignment](#judging-criteria-alignment)
10. [Code Templates](#code-templates)

---

## 🎯 EXECUTIVE SUMMARY

**Project Name:** RepoPilot AI - Repository-Grounded Engineering Assistant

**Core Value Proposition:**  
An AI assistant that deeply understands your codebase and refuses to hallucinate. Unlike generic coding assistants, RepoPilot grounds every answer in your actual repository, respects existing patterns, and shows engineering judgment by refusing unsafe operations.

**Key Differentiators:**
- ✅ Zero hallucination (repository-only knowledge)
- ✅ Pattern-aware code generation
- ✅ Confidence scoring on every response
- ✅ Smart refusal with explanations
- ✅ Impact visualization for changes
- ✅ Multi-layer repository understanding

---

## 📖 PROBLEM UNDERSTANDING

### What PS-2 Demands

**Core Challenge:**  
Build a Retrieval-Augmented Generation (RAG) system that:
1. Ingests a real GitHub repository
2. Acts as a repository-grounded engineering assistant
3. Prioritizes deep repository understanding
4. Uses cautious generation
5. Makes code-aware, explainable decisions

**Critical Constraints:**
- ❌ No hallucination allowed
- ❌ Must ground all answers in repository content
- ❌ Cannot use external knowledge without documentation
- ✅ Must decompose complex queries
- ✅ Must explain decisions and risks
- ✅ Must refuse when information is insufficient

### Success Metrics (Round 1)

**Required Deliverables:**
1. Documented ingestion & indexing process
2. RAG-grounded Q&A demonstration on developer prompts
3. Generated code examples with explanations
4. Generated PyTest files
5. Design document describing agents, data flow, grounding strategy
6. Clear list of repository assumptions and limitations

---

## 🏗️ SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│              (Streamlit / CLI / Web)                     │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│                 QUERY PROCESSOR                          │
│  • Intent Detection                                      │
│  • Query Decomposition                                   │
│  • Context Gathering                                     │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              REPOSITORY INTELLIGENCE LAYER               │
├──────────────────┬──────────────────┬───────────────────┤
│  Syntactic Layer │ Semantic Layer   │ Architectural     │
│  • File tree     │ • Function roles │ • Patterns        │
│  • Imports       │ • Class purposes │ • Conventions     │
│  • Dependencies  │ • Module intent  │ • Architecture    │
└──────────────────┴──────────────────┴───────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│                 RETRIEVAL ENGINE (RAG)                   │
│  • Vector Store (FAISS/ChromaDB)                        │
│  • Semantic Search                                       │
│  • Chunk Ranking                                         │
│  • Context Assembly                                      │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│                   DECISION ROUTER                        │
│  ┌────────────┬──────────────┬─────────────────┐       │
│  │  EXPLAIN   │  GENERATE    │    REFUSE       │       │
│  │  (Safe)    │  (Validated) │  (Unsafe/Risky) │       │
│  └────────────┴──────────────┴─────────────────┘       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              GENERATION & VALIDATION                     │
│  • Pattern Matcher                                       │
│  • Code Generator                                        │
│  • Risk Analyzer                                         │
│  • Confidence Scorer                                     │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│                  RESPONSE FORMATTER                      │
│  • Explanation Builder                                   │
│  • Impact Visualizer                                     │
│  • Source Attribution                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 CORE COMPONENTS

### 1. Repository Ingestion Engine

**Purpose:** Load and parse the entire GitHub repository

**Key Functions:**
- Clone repository or accept local path
- Walk directory tree
- Filter code files (ignore .git, node_modules, etc.)
- Extract metadata (language, LOC, imports)

**Output:**
```python
{
    "files": [
        {
            "path": "src/auth/login.py",
            "content": "...",
            "language": "python",
            "imports": ["flask", "bcrypt"],
            "functions": ["authenticate", "hash_password"],
            "loc": 145
        }
    ],
    "structure": {
        "src/": ["auth/", "models/", "utils/"],
        ...
    }
}
```

### 2. Repository Structure Analyzer

**Purpose:** Build a multi-layer understanding of the codebase

**Three Intelligence Layers:**

#### Layer 1: Syntactic Intelligence
- File tree and folder hierarchy
- Import graph (who imports whom)
- Dependency mapping
- File type distribution

#### Layer 2: Semantic Intelligence
- Function/class purposes (from docstrings/comments)
- Module responsibilities
- API endpoints and routes
- Configuration patterns

#### Layer 3: Architectural Intelligence
- Design pattern detection (MVC, Repository, Factory, etc.)
- Layering rules (controller → service → data)
- Naming conventions (camelCase vs snake_case)
- Testing patterns (pytest vs unittest)

**Output:**
```json
{
    "architecture": "MVC",
    "framework": "Flask",
    "patterns": {
        "auth": "decorator-based",
        "database": "SQLAlchemy ORM",
        "testing": "pytest with fixtures"
    },
    "conventions": {
        "naming": "snake_case",
        "docstrings": "Google style",
        "imports": "absolute"
    },
    "layers": {
        "controllers": ["src/routes/"],
        "services": ["src/services/"],
        "models": ["src/models/"]
    }
}
```

### 3. Vector Store & Embedding System

**Purpose:** Enable semantic search over code

**Implementation Steps:**

1. **Chunking Strategy:**
   - Function-level chunks (preferred)
   - Class-level chunks
   - File-level for small files
   - Sliding window for large files (overlap 20%)

2. **Metadata Enrichment:**
   Each chunk stores:
   ```python
   {
       "text": "def authenticate(user, password)...",
       "file_path": "src/auth/login.py",
       "chunk_type": "function",
       "language": "python",
       "imports": ["bcrypt"],
       "layer": "service"
   }
   ```

3. **Embedding Model:**
   - Use: `sentence-transformers/all-MiniLM-L6-v2` (fast, good quality)
   - Alternative: `text-embedding-ada-002` (OpenAI, higher quality)

4. **Vector Store:**
   - Development: FAISS (local, fast)
   - Production: ChromaDB or Pinecone

### 4. Query Processor & Decomposer

**Purpose:** Understand user intent and break down complex queries

**Query Types:**
```python
QUERY_INTENTS = {
    "explain": ["how does", "what is", "explain", "show me"],
    "generate": ["add", "create", "implement", "write"],
    "refactor": ["change", "modify", "improve", "refactor"],
    "debug": ["fix", "error", "bug", "issue"],
    "test": ["test", "pytest", "unittest"]
}
```

**Decomposition Example:**
```
User: "Add Redis caching to the checkout flow and write tests"

Decomposed:
1. Understand checkout flow
2. Check if Redis exists
3. Identify cache points
4. Generate cache implementation
5. Generate test cases
```

### 5. Grounded Retrieval System

**Purpose:** Fetch ONLY relevant repository content

**Retrieval Pipeline:**

1. **Semantic Search:**
   ```python
   # Query: "How does authentication work?"
   # Retrieve top 10 chunks with similarity > 0.7
   relevant_chunks = vector_store.similarity_search(
       query_embedding, 
       k=10, 
       threshold=0.7
   )
   ```

2. **Re-ranking:**
   - Prioritize chunks from core modules
   - Boost chunks with imports matching query
   - Downrank test files (unless query is about tests)

3. **Context Expansion:**
   - Fetch full file if chunk is too small
   - Include imported modules if mentioned
   - Add related classes/functions

4. **Context Window Management:**
   - Keep retrieved context under 4K tokens
   - Prioritize most relevant chunks
   - Include file paths for reference

### 6. Decision Router

**Purpose:** Decide whether to explain, generate, or refuse

**Decision Logic:**

```python
def route_decision(query, retrieved_context, confidence):
    if confidence < 0.5:
        return "REFUSE", "Insufficient information"
    
    if is_read_only_query(query):
        return "EXPLAIN", None
    
    if is_generation_query(query):
        if has_clear_patterns(retrieved_context):
            if risk_level(query) == "LOW":
                return "GENERATE", None
            else:
                return "REFUSE", "High risk: manual review needed"
        else:
            return "REFUSE", "Unclear patterns, need clarification"
    
    return "EXPLAIN", None
```

**Refusal Triggers:**
- Confidence score < 50%
- Conflicting patterns found
- Missing critical dependencies
- High-risk operations (auth, payments, security)
- Ambiguous requirements

### 7. Code Generator (Pattern-Aware)

**Purpose:** Generate code that matches repository style

**Generation Pipeline:**

1. **Pattern Extraction:**
   ```python
   patterns = {
       "function_style": "def function_name(arg1: Type) -> ReturnType:",
       "docstring": "Google style with Args and Returns",
       "error_handling": "try-except with logging",
       "imports": "absolute imports at top"
   }
   ```

2. **Template Selection:**
   - Use existing similar code as template
   - Extract structure, replace specifics

3. **Style Matching:**
   - Apply naming conventions
   - Match indentation (2 vs 4 spaces)
   - Follow import ordering

4. **Validation:**
   - Check syntax (AST parsing)
   - Verify imports exist
   - Ensure no layer violations

### 8. Confidence Scoring System

**Purpose:** Show how certain the system is

**Scoring Factors:**

```python
confidence = calculate_confidence(
    similarity_score=0.85,      # Vector similarity (40% weight)
    pattern_matches=5,           # Similar patterns found (30% weight)
    context_completeness=0.9,    # Has all needed context (20% weight)
    ambiguity_score=0.1          # Query clarity (10% weight)
)

# Output: 82% confidence
```

**Display Format:**
```
Confidence: 82% ████████▒▒

Based on:
  ✓ Found 5 similar authentication implementations
  ✓ All dependencies present (bcrypt, flask)
  ⚠ No existing test coverage for this module
  ⚠ Error handling pattern inconsistent
```

### 9. Risk Analyzer

**Purpose:** Assess impact and danger of changes

**Risk Categories:**

```python
RISK_LEVELS = {
    "LOW": {
        "changes": ["adding logs", "renaming variables", "adding comments"],
        "impact": "Single file, no dependency changes"
    },
    "MEDIUM": {
        "changes": ["adding functions", "refactoring logic", "adding tests"],
        "impact": "Multiple files, localized changes"
    },
    "HIGH": {
        "changes": ["auth changes", "database schema", "API contracts"],
        "impact": "Breaking changes, external dependencies affected"
    }
}
```

**Risk Output:**
```
Risk Assessment: MEDIUM

Impact:
  • 3 files will be modified
  • 7 files import these modules
  • No breaking API changes detected
  
Recommendations:
  ✓ Add integration tests
  ✓ Update API documentation
  ⚠ Review error handling in dependent modules
```

### 10. Explainability Engine

**Purpose:** Show reasoning for every decision

**Explanation Components:**

1. **Source Attribution:**
   ```
   Based on files:
     • src/auth/login.py (lines 45-67)
     • src/middleware/auth.py (lines 12-34)
     • config/security.py (lines 5-15)
   ```

2. **Reasoning Chain:**
   ```
   Reasoning:
   1. Query asks about authentication flow
   2. Retrieved 3 auth-related modules
   3. Identified decorator-based pattern
   4. Found session management in middleware
   5. Configuration uses environment variables
   ```

3. **Assumptions Made:**
   ```
   Assumptions:
     • Sessions stored in Redis (found in config)
     • Token expiry is 1 hour (config/security.py)
     • No OAuth implementation (not found)
   ```

4. **Limitations:**
   ```
   Cannot determine:
     • Rate limiting strategy (no implementation found)
     • Password reset flow (incomplete code)
     • Multi-factor authentication (not implemented)
   ```

---

## 🗓️ IMPLEMENTATION ROADMAP

### Day 1 - Morning (4 hours): Foundation

**Hour 1-2: Repository Ingestion**
```python
# Tasks:
✓ Set up GitHub API integration
✓ Implement file walker
✓ Parse code files (Python, JS, etc.)
✓ Extract basic metadata (LOC, imports)

# Deliverable: JSON dump of repository structure
```

**Hour 3-4: Vector Store Setup**
```python
# Tasks:
✓ Implement chunking logic
✓ Generate embeddings
✓ Initialize FAISS/ChromaDB
✓ Test semantic search

# Deliverable: Working search over code chunks
```

### Day 1 - Afternoon (4 hours): Intelligence Layers

**Hour 5-6: Structure Analyzer**
```python
# Tasks:
✓ Build import graph
✓ Detect file layers (controller/service/model)
✓ Extract naming conventions
✓ Identify framework/architecture

# Deliverable: Repository intelligence JSON
```

**Hour 7-8: Query Processor**
```python
# Tasks:
✓ Implement intent detection
✓ Build query decomposer
✓ Create routing logic
✓ Test with sample queries

# Deliverable: Query → Intent → Retrieval plan
```

### Day 1 - Evening (4 hours): Core RAG System

**Hour 9-10: Grounded Retrieval**
```python
# Tasks:
✓ Implement retrieval pipeline
✓ Add re-ranking logic
✓ Context expansion (fetch full files)
✓ Test retrieval quality

# Deliverable: Query → Relevant code chunks
```

**Hour 11-12: Basic Q&A**
```python
# Tasks:
✓ Integrate LLM (Claude/GPT-4)
✓ Build prompt templates
✓ Implement explanation generation
✓ Test on 10 sample questions

# Deliverable: Working Q&A system
```

### Day 2 - Morning (4 hours): Smart Generation

**Hour 13-14: Pattern Detector**
```python
# Tasks:
✓ Extract coding patterns
✓ Build pattern matcher
✓ Implement style checker
✓ Test pattern consistency

# Deliverable: Pattern compliance checker
```

**Hour 15-16: Code Generator**
```python
# Tasks:
✓ Implement template-based generation
✓ Add style matching
✓ Syntax validation
✓ Test on 5 generation tasks

# Deliverable: Pattern-aware code generator
```

### Day 2 - Afternoon (4 hours): Intelligence & Safety

**Hour 17-18: Confidence & Risk**
```python
# Tasks:
✓ Implement confidence scoring
✓ Build risk analyzer
✓ Create refusal logic
✓ Test edge cases

# Deliverable: Scored responses with risk labels
```

**Hour 19-20: Test Generator**
```python
# Tasks:
✓ Extract test patterns
✓ Implement pytest generator
✓ Match existing test style
✓ Generate 5 sample tests

# Deliverable: Auto-generated PyTest files
```

### Day 2 - Evening (4 hours): Polish & Demo

**Hour 21-22: UI Development**
```python
# Tasks:
✓ Build Streamlit/CLI interface
✓ Add visualizations (confidence, risk, impact)
✓ Implement file reference display
✓ Add example queries

# Deliverable: Demo-ready interface
```

**Hour 23-24: Demo Preparation**
```python
# Tasks:
✓ Prepare 5 demo scenarios
✓ Record failure cases (refusals)
✓ Create presentation slides
✓ Practice pitch (5 minutes)

# Deliverable: Polished demo + pitch deck
```

---

## 💻 TECHNICAL STACK

### Core Technologies

**Programming Language:**
- Python 3.9+ (best ecosystem for AI/ML)

**LLM Integration:**
```python
# Option 1: Claude API (Anthropic)
import anthropic
client = anthropic.Anthropic(api_key="...")

# Option 2: OpenAI GPT-4
import openai
client = openai.OpenAI(api_key="...")

# Option 3: Local (Ollama + Llama)
import ollama
response = ollama.chat(model='llama2')
```

**Vector Store:**
```python
# Option 1: FAISS (local, fast)
import faiss
index = faiss.IndexFlatL2(dimension)

# Option 2: ChromaDB (persistent, easy)
import chromadb
client = chromadb.Client()

# Option 3: Pinecone (cloud, scalable)
import pinecone
pinecone.init(api_key="...")
```

**Embedding Models:**
```python
# Option 1: Sentence Transformers (free, local)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')

# Option 2: OpenAI Embeddings (paid, high quality)
import openai
embedding = openai.Embedding.create(input="text")
```

**Code Parsing:**
```python
# Python AST parsing
import ast
tree = ast.parse(code)

# Multi-language parsing
from tree_sitter import Language, Parser
parser = Parser()
```

**UI Framework:**
```python
# Option 1: Streamlit (fastest)
import streamlit as st

# Option 2: Gradio (AI-focused)
import gradio as gr

# Option 3: Flask + React (custom)
from flask import Flask
```

### Recommended Stack

```
┌─────────────────────────────────────┐
│         LLM: Claude Sonnet 4.5      │ (Best for coding)
├─────────────────────────────────────┤
│    Embeddings: all-MiniLM-L6-v2     │ (Free, good quality)
├─────────────────────────────────────┤
│      Vector Store: ChromaDB         │ (Easy persistence)
├─────────────────────────────────────┤
│     Code Parsing: AST + tree-sitter │ (Multi-language)
├─────────────────────────────────────┤
│         UI: Streamlit               │ (Rapid development)
├─────────────────────────────────────┤
│     GitHub: PyGithub API            │ (Repository access)
└─────────────────────────────────────┘
```

---

## 🎨 FEATURE DETAILS

### Feature 1: Repository Health Dashboard

**What It Shows:**
```
┌─ Repository Health ────────────────────────┐
│                                             │
│  Overall Score: 87/100  ████████▒▒         │
│                                             │
│  📊 Metrics:                                │
│    Code Coverage:      76% ███████▒▒▒      │
│    Documentation:      82% ████████▒▒      │
│    Pattern Consistency: 91% █████████▒     │
│    Complexity:         Medium              │
│                                             │
│  🔍 Detected:                               │
│    • Framework: Flask 2.x                  │
│    • Architecture: MVC                     │
│    • Testing: pytest + fixtures            │
│    • DB: PostgreSQL + SQLAlchemy           │
│                                             │
│  ⚠️ Issues:                                 │
│    • 3 files missing docstrings            │
│    • 2 inconsistent naming patterns        │
│    • No caching layer found                │
└────────────────────────────────────────────┘
```

**Implementation:**
```python
def calculate_health_score(repo_data):
    scores = {
        "documentation": count_docstrings(repo_data) / total_functions,
        "consistency": check_naming_patterns(repo_data),
        "complexity": analyze_cyclomatic_complexity(repo_data),
        "testing": count_test_files(repo_data) / count_source_files(repo_data)
    }
    return weighted_average(scores)
```

### Feature 2: Confidence Visualization

**Display Format:**
```
┌─ Response Confidence ──────────────────────┐
│                                             │
│  Overall: 82% ████████▒▒                   │
│                                             │
│  Breakdown:                                 │
│    Retrieval Quality:   95% █████████▒     │
│    Pattern Match:       80% ████████       │
│    Context Complete:    90% █████████      │
│    Query Clarity:       65% ██████▒▒▒▒     │
│                                             │
│  Evidence:                                  │
│    ✓ 5 similar implementations found       │
│    ✓ All imports available                 │
│    ⚠ No test coverage exists               │
│    ⚠ Edge case handling unclear            │
│                                             │
│  Recommendation: MEDIUM confidence          │
│  Suggest: Review generated code carefully   │
└────────────────────────────────────────────┘
```

### Feature 3: Change Impact Visualization

**Visual Output:**
```
┌─ Change Impact Analysis ───────────────────┐
│                                             │
│  Proposed: Add Redis caching to checkout   │
│                                             │
│  Direct Impact:                             │
│    🔴 src/services/checkout.py (MODIFY)    │
│    🟡 src/config/cache.py      (CREATE)    │
│    🟢 tests/test_checkout.py   (UPDATE)    │
│                                             │
│  Ripple Effects: (7 files)                 │
│    src/routes/checkout_routes.py           │
│    src/services/payment.py                 │
│    src/services/inventory.py               │
│    ... (4 more)                            │
│                                             │
│  Risk Level: MEDIUM                         │
│    • No breaking API changes               │
│    • New dependency: redis-py              │
│    • Requires testing: cache invalidation  │
│                                             │
│  Recommendations:                           │
│    1. Add integration tests                │
│    2. Configure Redis in docker-compose    │
│    3. Add cache monitoring                 │
└────────────────────────────────────────────┘
```

### Feature 4: Smart Refusal Examples

**Example 1: Missing Context**
```
❌ Cannot proceed: Insufficient information

Reason:
  Your request: "Add authentication to the API"
  
  Issues:
    • No authentication system found in repository
    • 3 different auth patterns seen in comments
    • Missing: user model, session management, token handling
  
  Before I can help:
    1. Clarify which auth approach (JWT vs Session vs OAuth)
    2. Point me to existing user model (if any)
    3. Specify security requirements (2FA, rate limiting, etc.)

Alternative: Would you like me to:
  → Explain common auth patterns first?
  → Show examples from similar projects?
  → Help design an auth architecture?
```

**Example 2: High Risk Operation**
```
⚠️ Refusing: High-risk change

Your request: "Modify the database schema to add user_role"

Risk factors:
  🔴 Database migration (potential data loss)
  🔴 17 files query the user table
  🔴 No rollback strategy detected
  🔴 Production database (based on config)

This requires:
  ✓ Manual review by senior engineer
  ✓ Backup strategy
  ✓ Migration testing on staging
  ✓ Rollback plan

I can help with:
  → Generate migration script (for review)
  → Identify affected queries
  → Suggest testing strategy
  → Document rollback steps

But I cannot auto-execute this change.
```

**Example 3: Conflicting Patterns**
```
⚠️ Cannot generate: Conflicting patterns detected

Your request: "Add error handling to login function"

Problem:
  Found 3 different error handling styles:
  
  Style A (5 files):
    try-except with custom exceptions
    Example: raise AuthenticationError("Invalid credentials")
  
  Style B (3 files):
    Return tuple (success, error_msg)
    Example: return False, "Invalid credentials"
  
  Style C (2 files):
    HTTP status codes directly
    Example: return jsonify(error=...), 401

Which style should I follow?

Or would you like me to:
  → Recommend standardizing on one approach?
  → Show pros/cons of each style?
```

### Feature 5: Pattern Violation Detector

**Real-time Warnings:**
```python
# Generated code:
def getUserData(userId):  # ⚠️ Pattern violation!
    return db.query(User).filter(id=userId)

# Warning shown:
┌─ Pattern Violation Detected ───────────────┐
│                                             │
│  ⚠️ Function name uses camelCase            │
│                                             │
│  Repository convention: snake_case          │
│    Evidence: 47/50 functions use snake_case│
│                                             │
│  Suggested fix:                             │
│    def get_user_data(user_id):              │
│        return db.query(User).filter(...)    │
│                                             │
│  Other issues:                              │
│    • Direct DB query in function            │
│      (Repository pattern suggests using     │
│       UserRepository.find_by_id())          │
│                                             │
│  [Apply Fix] [Ignore] [Explain More]        │
└────────────────────────────────────────────┘
```

### Feature 6: Context-Aware Test Generation

**Input:**
```python
# Source code:
def calculate_discount(price, user_tier):
    if user_tier == "premium":
        return price * 0.8
    elif user_tier == "gold":
        return price * 0.9
    return price
```

**Generated Test (matching repo style):**
```python
# tests/test_pricing.py
import pytest
from src.pricing import calculate_discount

class TestCalculateDiscount:
    """Test suite for discount calculation logic."""
    
    @pytest.fixture
    def base_price(self):
        """Standard test price fixture."""
        return 100.0
    
    def test_premium_discount(self, base_price):
        """Premium users get 20% discount."""
        result = calculate_discount(base_price, "premium")
        assert result == 80.0
    
    def test_gold_discount(self, base_price):
        """Gold users get 10% discount."""
        result = calculate_discount(base_price, "gold")
        assert result == 90.0
    
    def test_regular_user_no_discount(self, base_price):
        """Regular users pay full price."""
        result = calculate_discount(base_price, "regular")
        assert result == base_price
    
    @pytest.mark.parametrize("user_tier,expected_multiplier", [
        ("premium", 0.8),
        ("gold", 0.9),
        ("regular", 1.0),
    ])
    def test_discount_tiers(self, base_price, user_tier, expected_multiplier):
        """Parameterized test for all discount tiers."""
        expected = base_price * expected_multiplier
        result = calculate_discount(base_price, user_tier)
        assert result == expected

# Note: Matches repository test style:
# ✓ Class-based organization
# ✓ Fixtures for common test data
# ✓ Descriptive docstrings
# ✓ Parametrized tests for multiple cases
# ✓ Uses pytest (not unittest)
```

---

## 🎪 DEMO STRATEGY

### Demo Flow (5 Minutes)

**Slide 1: The Problem (30 seconds)**
```
"Every AI assistant hallucinates.
They suggest code that doesn't match your patterns.
They ignore your architecture.
They guess when they should refuse.

What if AI could actually understand your codebase?"
```

**Slide 2: The Solution (30 seconds)**
```
"Meet RepoPilot AI.
The only assistant that grounds every answer in YOUR repository.
Zero hallucination. Pattern-aware. Engineering judgment."
```

**Demo Part 1: Simple Q&A (60 seconds)**
```
Action:
1. Show repository ingestion (live or pre-recorded)
   → Structure map appears
   → Health dashboard shows 87/100
   → Patterns detected: Flask, MVC, pytest

2. Ask: "How does authentication work in this project?"
   
   System shows:
   ✓ Confidence: 92%
   ✓ Retrieved 3 files (shown)
   ✓ Explains decorator-based auth
   ✓ Shows session management
   ✓ Attributes sources

Talking point: "Notice - it shows WHICH files it used. No mystery."
```

**Demo Part 2: Smart Refusal (60 seconds)**
```
Action:
Ask: "Add payment processing with Stripe to the checkout flow"

System responds:
  ❌ Cannot proceed safely
  
  Reason shown:
    • No Stripe integration found
    • Payment handling is HIGH RISK
    • Security requirements unclear
    • PCI compliance needs review
  
  Alternative offered:
    → Show best practices first?
    → Design payment architecture?
    → Generate integration plan?

Talking point: "This is engineering maturity. It refuses to guess on critical systems."
```

**Demo Part 3: Pattern-Aware Generation (90 seconds)**
```
Action:
Ask: "Add a caching layer to the product search"

System shows:
  1. Confidence: 78%
  2. Analysis:
     ✓ Redis imported but unused
     ✓ Found similar caching in user service
     ✓ Pattern: decorator-based caching
  
  3. Generated code:
     → Matches repository style (snake_case)
     → Uses existing Redis config
     → Follows decorator pattern
     → Includes error handling
  
  4. Impact visualization:
     🟡 2 files modified
     🟢 No breaking changes
     Risk: MEDIUM
  
  5. Generated tests:
     → Matches pytest style
     → Uses fixtures like existing tests
     → Includes edge cases

Talking point: "Not just code generation - it understands YOUR patterns and follows them."
```

**Demo Part 4: Explainability (30 seconds)**
```
Action:
Show the "Explain Decision" toggle

Reveals:
  • Which files were searched
  • Why this approach was chosen
  • What patterns were detected
  • What assumptions were made
  • What could go wrong

Talking point: "Complete transparency. You can audit every decision."
```

**Closing Statement (30 seconds)**
```
"RepoPilot isn't about generating more code.
It's about generating the RIGHT code.
Code that respects your architecture.
Code that follows your patterns.
With the judgment to refuse when it should.

This is AI that thinks like an engineer."

[Show GitHub repo and live demo link]
```

---

## 📊 JUDGING CRITERIA ALIGNMENT

### How RepoPilot Scores on Key Criteria

**1. Repository Understanding (30% weight)**
```
✅ Three-layer intelligence (syntactic, semantic, architectural)
✅ Pattern detection and consistency checking
✅ Import graph and dependency mapping
✅ Framework/architecture auto-detection
✅ Naming convention extraction

Score: 9/10 (Industry-leading depth)
```

**2. Grounded RAG (25% weight)**
```
✅ Vector store with semantic search
✅ Chunk-level and file-level retrieval
✅ Context expansion with imports
✅ Re-ranking by relevance
✅ Zero external knowledge usage

Score: 10/10 (Perfect compliance with PS-2)
```

**3. Safe Generation (20% weight)**
```
✅ Confidence scoring on every response
✅ Risk analysis (LOW/MEDIUM/HIGH)
✅ Smart refusal with explanations
✅ Pattern violation detection
✅ Hallucination prevention

Score: 9/10 (Shows engineering maturity)
```

**4. Code Quality (15% weight)**
```
✅ Pattern-aware generation
✅ Style matching (naming, formatting)
✅ Syntax validation
✅ Test generation (matching repo style)
✅ Documentation generation

Score: 8/10 (Strong, practical implementation)
```

**5. Explainability (10% weight)**
```
✅ Source attribution for every answer
✅ Reasoning chain visible
✅ Assumptions documented
✅ Limitations stated clearly
✅ "Show your work" mode

Score: 9/10 (Best-in-class transparency)
```

**Overall Projected Score: 8.9/10**

---

## 💻 CODE TEMPLATES

### Template 1: Repository Ingestion

```python
# repo_ingestion.py

import os
import ast
from pathlib import Path
from typing import List, Dict
import git

class RepositoryIngester:
    """Load and parse a GitHub repository."""
    
    IGNORED_DIRS = {'.git', 'node_modules', '__pycache__', 'venv', '.env'}
    CODE_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go'}
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.files = []
        self.structure = {}
        
    def ingest(self) -> Dict:
        """Main ingestion pipeline."""
        print(f"🔍 Scanning repository: {self.repo_path}")
        
        self._walk_directory()
        self._parse_files()
        self._build_structure()
        self._extract_metadata()
        
        return {
            "files": self.files,
            "structure": self.structure,
            "metadata": self.metadata
        }
    
    def _walk_directory(self):
        """Walk through directory tree."""
        for root, dirs, files in os.walk(self.repo_path):
            # Remove ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
            
            for file in files:
                if Path(file).suffix in self.CODE_EXTENSIONS:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(self.repo_path)
                    
                    self.files.append({
                        "path": str(relative_path),
                        "absolute_path": str(file_path),
                        "language": self._detect_language(file)
                    })
    
    def _parse_files(self):
        """Parse code files and extract information."""
        for file_data in self.files:
            try:
                with open(file_data["absolute_path"], 'r', encoding='utf-8') as f:
                    content = f.read()
                    file_data["content"] = content
                    file_data["loc"] = len(content.splitlines())
                    
                    if file_data["language"] == "python":
                        file_data["ast_info"] = self._parse_python(content)
                        
            except Exception as e:
                print(f"⚠️  Error parsing {file_data['path']}: {e}")
                file_data["error"] = str(e)
    
    def _parse_python(self, content: str) -> Dict:
        """Extract Python-specific information."""
        try:
            tree = ast.parse(content)
            
            imports = []
            functions = []
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module)
                elif isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "lineno": node.lineno,
                        "args": [arg.arg for arg in node.args.args]
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "lineno": node.lineno
                    })
            
            return {
                "imports": list(set(imports)),
                "functions": functions,
                "classes": classes
            }
        except:
            return {}
    
    def _detect_language(self, filename: str) -> str:
        """Detect programming language from extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go'
        }
        return ext_map.get(Path(filename).suffix, 'unknown')
    
    def _build_structure(self):
        """Build directory tree structure."""
        for file_data in self.files:
            parts = Path(file_data["path"]).parts
            current = self.structure
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
    
    def _extract_metadata(self):
        """Extract high-level repository metadata."""
        total_loc = sum(f.get("loc", 0) for f in self.files)
        languages = {}
        
        for file_data in self.files:
            lang = file_data["language"]
            languages[lang] = languages.get(lang, 0) + 1
        
        self.metadata = {
            "total_files": len(self.files),
            "total_loc": total_loc,
            "languages": languages,
            "primary_language": max(languages, key=languages.get)
        }

# Usage:
ingester = RepositoryIngester("/path/to/repo")
repo_data = ingester.ingest()
```

### Template 2: Vector Store Setup

```python
# vector_store.py

from sentence_transformers import SentenceTransformer
import chromadb
from typing import List, Dict
import hashlib

class VectorStore:
    """Manage embeddings and semantic search."""
    
    def __init__(self, collection_name: str = "repo_code"):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.client = chromadb.Client()
        self.collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def chunk_code(self, file_data: Dict) -> List[Dict]:
        """Split code into searchable chunks."""
        chunks = []
        
        if file_data["language"] == "python" and "ast_info" in file_data:
            # Function-level chunking for Python
            content = file_data["content"]
            lines = content.splitlines()
            
            for func in file_data["ast_info"].get("functions", []):
                start_line = func["lineno"] - 1
                # Find function end (simple heuristic)
                end_line = start_line + 20  # Adjust as needed
                
                chunk_text = "\n".join(lines[start_line:end_line])
                chunks.append({
                    "text": chunk_text,
                    "type": "function",
                    "name": func["name"],
                    "file_path": file_data["path"],
                    "language": file_data["language"]
                })
        else:
            # Sliding window for other files
            content = file_data["content"]
            lines = content.splitlines()
            window_size = 50
            overlap = 10
            
            for i in range(0, len(lines), window_size - overlap):
                chunk_text = "\n".join(lines[i:i+window_size])
                chunks.append({
                    "text": chunk_text,
                    "type": "window",
                    "file_path": file_data["path"],
                    "language": file_data["language"],
                    "start_line": i
                })
        
        return chunks
    
    def index_repository(self, repo_data: Dict):
        """Index all repository code."""
        all_chunks = []
        
        print("📦 Chunking code files...")
        for file_data in repo_data["files"]:
            chunks = self.chunk_code(file_data)
            all_chunks.extend(chunks)
        
        print(f"🔢 Generated {len(all_chunks)} chunks")
        print("🧮 Generating embeddings...")
        
        # Generate embeddings in batches
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i+batch_size]
            texts = [chunk["text"] for chunk in batch]
            embeddings = self.model.encode(texts).tolist()
            
            # Create unique IDs
            ids = [hashlib.md5(chunk["text"].encode()).hexdigest() 
                   for chunk in batch]
            
            # Prepare metadata
            metadatas = [
                {
                    "file_path": chunk["file_path"],
                    "type": chunk["type"],
                    "language": chunk["language"]
                }
                for chunk in batch
            ]
            
            # Add to ChromaDB
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )
        
        print("✅ Indexing complete!")
    
    def search(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search for relevant code chunks."""
        query_embedding = self.model.encode([query])[0].tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "similarity": 1 - results["distances"][0][i]
            })
        
        return formatted

# Usage:
vector_store = VectorStore()
vector_store.index_repository(repo_data)
results = vector_store.search("authentication function")
```

### Template 3: Query Processor

```python
# query_processor.py

from typing import Dict, List, Tuple
import re

class QueryProcessor:
    """Process and understand user queries."""
    
    INTENT_PATTERNS = {
        "explain": [
            r"how does .* work",
            r"what is",
            r"explain",
            r"show me",
            r"describe",
            r"tell me about"
        ],
        "generate": [
            r"add",
            r"create",
            r"implement",
            r"write",
            r"build",
            r"make"
        ],
        "refactor": [
            r"change",
            r"modify",
            r"improve",
            r"refactor",
            r"update",
            r"optimize"
        ],
        "debug": [
            r"fix",
            r"error",
            r"bug",
            r"issue",
            r"problem",
            r"not working"
        ],
        "test": [
            r"test",
            r"pytest",
            r"unittest",
            r"test case"
        ]
    }
    
    def process(self, query: str) -> Dict:
        """Process user query and extract intent."""
        query_lower = query.lower()
        
        intent = self._detect_intent(query_lower)
        entities = self._extract_entities(query)
        complexity = self._assess_complexity(query)
        
        return {
            "original": query,
            "intent": intent,
            "entities": entities,
            "complexity": complexity,
            "decomposed": self._decompose_query(query, intent)
        }
    
    def _detect_intent(self, query: str) -> str:
        """Detect user intent from query."""
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    return intent
        return "explain"  # Default
    
    def _extract_entities(self, query: str) -> Dict:
        """Extract technical entities from query."""
        entities = {
            "files": re.findall(r'\b\w+\.py\b', query),
            "functions": re.findall(r'\b[a-z_]+\([^)]*\)', query),
            "classes": re.findall(r'\b[A-Z][a-zA-Z]*\b', query),
            "technologies": []
        }
        
        # Common tech keywords
        tech_keywords = ['redis', 'postgres', 'docker', 'api', 'rest', 
                        'auth', 'cache', 'database', 'jwt']
        for tech in tech_keywords:
            if tech in query.lower():
                entities["technologies"].append(tech)
        
        return entities
    
    def _assess_complexity(self, query: str) -> str:
        """Assess query complexity."""
        word_count = len(query.split())
        has_multiple_requests = " and " in query or " also " in query
        
        if word_count < 5 and not has_multiple_requests:
            return "simple"
        elif word_count < 15 and not has_multiple_requests:
            return "medium"
        else:
            return "complex"
    
    def _decompose_query(self, query: str, intent: str) -> List[str]:
        """Break complex queries into sub-queries."""
        if " and " in query:
            parts = query.split(" and ")
            return [part.strip() for part in parts]
        elif " also " in query:
            parts = query.split(" also ")
            return [part.strip() for part in parts]
        else:
            return [query]

# Usage:
processor = QueryProcessor()
query_info = processor.process("Add Redis caching to checkout and write tests")
# Returns: {
#   "intent": "generate",
#   "complexity": "complex",
#   "decomposed": ["Add Redis caching to checkout", "write tests"]
# }
```

### Template 4: Decision Router with Confidence

```python
# decision_router.py

from typing import Dict, Tuple, List

class DecisionRouter:
    """Route queries to appropriate actions."""
    
    def __init__(self):
        self.high_risk_keywords = [
            'auth', 'password', 'security', 'payment', 
            'database schema', 'migration', 'deploy'
        ]
    
    def route(self, query_info: Dict, retrieval_results: List[Dict]) -> Tuple[str, float, str]:
        """
        Route to action: EXPLAIN, GENERATE, or REFUSE.
        
        Returns: (action, confidence, reason)
        """
        confidence = self._calculate_confidence(retrieval_results)
        risk_level = self._assess_risk(query_info)
        intent = query_info["intent"]
        
        # Decision logic
        if confidence < 0.5:
            return (
                "REFUSE",
                confidence,
                f"Insufficient information (confidence: {confidence:.0%})"
            )
        
        if intent in ["explain", "debug"]:
            # Read-only queries are safe
            return ("EXPLAIN", confidence, "Safe read-only operation")
        
        if intent in ["generate", "refactor"]:
            if risk_level == "HIGH":
                return (
                    "REFUSE",
                    confidence,
                    f"High-risk operation requires manual review: {risk_level}"
                )
            elif confidence > 0.7 and risk_level == "LOW":
                return ("GENERATE", confidence, "Safe generation with clear patterns")
            else:
                return (
                    "REFUSE",
                    confidence,
                    "Unclear patterns or medium risk - need clarification"
                )
        
        return ("EXPLAIN", confidence, "Default safe action")
    
    def _calculate_confidence(self, results: List[Dict]) -> float:
        """Calculate confidence score."""
        if not results:
            return 0.0
        
        # Factors:
        # 1. Similarity scores (40%)
        avg_similarity = sum(r.get("similarity", 0) for r in results) / len(results)
        
        # 2. Number of good matches (30%)
        good_matches = sum(1 for r in results if r.get("similarity", 0) > 0.7)
        match_score = min(good_matches / 3, 1.0)  # 3+ matches = 100%
        
        # 3. Consistency (30%)
        # Check if results are from related files
        file_paths = [r["metadata"]["file_path"] for r in results]
        unique_dirs = len(set(p.split('/')[0] for p in file_paths))
        consistency = 1.0 if unique_dirs <= 2 else 0.5
        
        confidence = (
            avg_similarity * 0.4 +
            match_score * 0.3 +
            consistency * 0.3
        )
        
        return confidence
    
    def _assess_risk(self, query_info: Dict) -> str:
        """Assess risk level of the query."""
        query_lower = query_info["original"].lower()
        
        # Check for high-risk keywords
        for keyword in self.high_risk_keywords:
            if keyword in query_lower:
                return "HIGH"
        
        # Check intent
        if query_info["intent"] in ["refactor"]:
            return "MEDIUM"
        
        return "LOW"

# Usage:
router = DecisionRouter()
action, confidence, reason = router.route(query_info, search_results)
```

### Template 5: Pattern-Aware Code Generator

```python
# code_generator.py

from typing import Dict, List
import re

class CodeGenerator:
    """Generate code that matches repository patterns."""
    
    def __init__(self, repo_intelligence: Dict):
        self.patterns = repo_intelligence.get("patterns", {})
        self.conventions = repo_intelligence.get("conventions", {})
    
    def generate(self, query_info: Dict, context: List[Dict]) -> Dict:
        """Generate code matching repository style."""
        
        # Extract patterns from context
        examples = [c["text"] for c in context[:3]]
        detected_style = self._detect_style(examples)
        
        # Generate code using LLM with style constraints
        prompt = self._build_prompt(query_info, context, detected_style)
        
        # Simulate generation (in real implementation, call LLM here)
        generated_code = self._call_llm(prompt)
        
        # Validate and check patterns
        violations = self._check_violations(generated_code, detected_style)
        
        return {
            "code": generated_code,
            "style": detected_style,
            "violations": violations,
            "confidence": 0.85 if not violations else 0.6
        }
    
    def _detect_style(self, examples: List[str]) -> Dict:
        """Detect coding style from examples."""
        style = {
            "naming": "snake_case",  # Default
            "indentation": 4,
            "quotes": "double",
            "docstring_style": "google"
        }
        
        # Detect naming convention
        snake_case_count = sum(1 for ex in examples if re.search(r'def [a-z_]+\(', ex))
        camel_case_count = sum(1 for ex in examples if re.search(r'def [a-z][a-zA-Z]+\(', ex))
        
        if camel_case_count > snake_case_count:
            style["naming"] = "camelCase"
        
        # Detect indentation
        for example in examples:
            match = re.search(r'\n( +)\w', example)
            if match:
                style["indentation"] = len(match.group(1))
                break
        
        # Detect quotes
        single_quotes = sum(ex.count("'") for ex in examples)
        double_quotes = sum(ex.count('"') for ex in examples)
        style["quotes"] = "single" if single_quotes > double_quotes else "double"
        
        return style
    
    def _build_prompt(self, query_info: Dict, context: List[Dict], style: Dict) -> str:
        """Build LLM prompt with style constraints."""
        prompt = f"""You are a code generator. Generate code that EXACTLY matches this style:

Naming: {style['naming']}
Indentation: {style['indentation']} spaces
Quotes: {style['quotes']}
Docstring: {style['docstring_style']} style

Task: {query_info['original']}

Context from repository:
"""
        for i, ctx in enumerate(context[:3], 1):
            prompt += f"\n--- Example {i} ---\n{ctx['text']}\n"
        
        prompt += "\nGenerate ONLY the code, matching the style above EXACTLY."
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM API (placeholder)."""
        # In real implementation:
        # response = claude_client.messages.create(
        #     model="claude-sonnet-4-5",
        #     messages=[{"role": "user", "content": prompt}]
        # )
        # return response.content[0].text
        
        # Placeholder for demonstration
        return '''def get_user_data(user_id):
    """Fetch user data from database.
    
    Args:
        user_id: The user identifier
        
    Returns:
        User object or None if not found
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None'''
    
    def _check_violations(self, code: str, style: Dict) -> List[str]:
        """Check for style violations."""
        violations = []
        
        # Check naming convention
        if style["naming"] == "snake_case":
            if re.search(r'def [a-z][a-zA-Z]+\(', code):
                violations.append("Found camelCase function (expected snake_case)")
        
        # Check indentation
        lines = code.split('\n')
        for line in lines:
            if line.startswith('    '):
                indent = len(line) - len(line.lstrip())
                if indent % style["indentation"] != 0:
                    violations.append(f"Inconsistent indentation (expected {style['indentation']} spaces)")
                    break
        
        return violations

# Usage:
generator = CodeGenerator(repo_intelligence)
result = generator.generate(query_info, search_results)
```

### Template 6: Complete Streamlit UI

```python
# app.py

import streamlit as st
from repo_ingestion import RepositoryIngester
from vector_store import VectorStore
from query_processor import QueryProcessor
from decision_router import DecisionRouter
from code_generator import CodeGenerator

def main():
    st.set_page_config(page_title="RepoPilot AI", layout="wide")
    
    # Header
    st.title("🚀 RepoPilot AI")
    st.markdown("*Repository-Grounded Engineering Assistant*")
    
    # Sidebar - Repository Setup
    with st.sidebar:
        st.header("📁 Repository Setup")
        repo_path = st.text_input("Repository Path:", "/path/to/repo")
        
        if st.button("🔄 Ingest Repository"):
            with st.spinner("Ingesting repository..."):
                # Ingest
                ingester = RepositoryIngester(repo_path)
                repo_data = ingester.ingest()
                st.session_state["repo_data"] = repo_data
                
                # Index
                vector_store = VectorStore()
                vector_store.index_repository(repo_data)
                st.session_state["vector_store"] = vector_store
                
                st.success("✅ Repository loaded!")
        
        if "repo_data" in st.session_state:
            st.markdown("---")
            st.subheader("📊 Repository Health")
            metadata = st.session_state["repo_data"]["metadata"]
            
            st.metric("Total Files", metadata["total_files"])
            st.metric("Lines of Code", f"{metadata['total_loc']:,}")
            st.metric("Primary Language", metadata["primary_language"])
    
    # Main Area
    if "repo_data" not in st.session_state:
        st.info("👈 Please ingest a repository to start")
        return
    
    # Query Input
    st.header("💬 Ask RepoPilot")
    query = st.text_area(
        "Enter your question or request:",
        placeholder="e.g., How does authentication work? or Add caching to product search",
        height=100
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        submit = st.button("🔍 Ask", type="primary")
    with col2:
        show_debug = st.checkbox("Show reasoning", value=False)
    
    if submit and query:
        # Process query
        processor = QueryProcessor()
        query_info = processor.process(query)
        
        # Search
        vector_store = st.session_state["vector_store"]
        search_results = vector_store.search(query, n_results=5)
        
        # Route decision
        router = DecisionRouter()
        action, confidence, reason = router.route(query_info, search_results)
        
        # Display results
        st.markdown("---")
        
        # Confidence bar
        col1, col2 = st.columns([3, 1])
        with col1:
            st.progress(confidence)
        with col2:
            st.metric("Confidence", f"{confidence:.0%}")
        
        # Show debug info
        if show_debug:
            with st.expander("🔍 Query Analysis"):
                st.json(query_info)
            
            with st.expander("📚 Retrieved Context"):
                for i, result in enumerate(search_results, 1):
                    st.markdown(f"**{i}. {result['metadata']['file_path']}** (similarity: {result['similarity']:.2%})")
                    st.code(result['text'][:200] + "...", language=result['metadata']['language'])
        
        # Action based on routing
        if action == "REFUSE":
            st.error(f"❌ Cannot proceed: {reason}")
            st.info("💡 Suggestion: Please provide more context or clarify your request.")
        
        elif action == "EXPLAIN":
            st.success("✅ Explanation")
            
            # Generate explanation (placeholder)
            st.markdown(f"""
            Based on the repository analysis:
            
            {reason}
            
            **Sources:**
            - {search_results[0]['metadata']['file_path']}
            - {search_results[1]['metadata']['file_path']}
            
            **Key Points:**
            - Authentication uses decorator-based approach
            - Session management via Redis
            - Token expiry: 1 hour
            """)
        
        elif action == "GENERATE":
            st.success(f"✅ Code Generated (confidence: {confidence:.0%})")
            
            # Generate code
            repo_intelligence = st.session_state["repo_data"].get("intelligence", {})
            generator = CodeGenerator(repo_intelligence)
            result = generator.generate(query_info, search_results)
            
            # Show violations if any
            if result["violations"]:
                st.warning("⚠️ Style Violations Detected:")
                for violation in result["violations"]:
                    st.markdown(f"- {violation}")
            
            # Show code
            st.code(result["code"], language="python")
            
            # Show metadata
            with st.expander("📝 Generation Details"):
                st.json(result["style"])

if __name__ == "__main__":
    main()
```

---

## 🎯 FINAL CHECKLIST

### Before Demo Day

**Technical Checklist:**
- [ ] Repository ingestion works on sample repo
- [ ] Vector search returns relevant results
- [ ] Query processor handles 5+ query types
- [ ] Confidence scoring shows on every response
- [ ] Smart refusal demonstrates at least once
- [ ] Code generation matches repository style
- [ ] Test generation produces valid pytest files
- [ ] UI is clean and professional
- [ ] Demo flows smoothly (practice 3+ times)
- [ ] GitHub repo is public and documented

**Demo Preparation:**
- [ ] 5-minute pitch prepared and timed
- [ ] Demo scenarios tested (happy path + refusal)
- [ ] Backup plan if live demo fails
- [ ] Slides ready (problem → solution → demo → impact)
- [ ] Team roles assigned (presenter, driver, responder)

**Documentation:**
- [ ] README with clear setup instructions
- [ ] Architecture diagram included
- [ ] Example queries documented
- [ ] Video demo recorded (backup)
- [ ] Design document (required deliverable)

---

## 🏆 WINNING FACTORS

### What Makes This Stand Out

**1. Engineering Maturity**
- Most teams will demo happy paths only
- You'll demo smart refusals (shows real-world thinking)
- Confidence scoring shows transparency
- Risk analysis shows production readiness

**2. Deep Understanding**
- Three-layer intelligence (syntactic, semantic, architectural)
- Pattern detection and enforcement
- Not just "search and answer" - actual understanding

**3. Practical Value**
- Solves real developer pain (understanding legacy code)
- Pattern-aware generation (not generic templates)
- Prevents hallucination (critical for production use)

**4. Visual Impact**
- Clean UI with confidence bars
- Impact visualization for changes
- Source attribution visible
- Health dashboard on load

**5. Technical Excellence**
- Proper RAG implementation (not just search)
- Multi-factor confidence scoring
- Context-aware test generation
- Explainable AI throughout

---

## 🚫 COMMON PITFALLS TO AVOID

### Don't Make These Mistakes

**1. Over-Engineering**
```
❌ Don't build 15 half-working features
✅ Build 9 core features that work perfectly
```

**2. Generic Demos**
```
❌ Don't demo on "hello world" repos
✅ Use a real, messy production-like repo
```

**3. Ignoring Refusal**
```
❌ Don't only show successful generation
✅ MUST demo smart refusal (judges love this)
```

**4. Poor Presentation**
```
❌ Don't wing the demo
✅ Practice 5+ times, have backup video
```

**5. Missing Documentation**
```
❌ Don't forget the design doc (required!)
✅ Document assumptions, architecture, limitations
```

**6. Weak Differentiation**
```
❌ Don't say "it's like ChatGPT for code"
✅ Say "it's the only assistant that refuses to hallucinate"
```

---

## 📚 ADDITIONAL RESOURCES

### Helpful Links

**RAG Implementation:**
- LangChain RAG Guide: https://python.langchain.com/docs/use_cases/question_answering/
- ChromaDB Documentation: https://docs.trychroma.com/
- Sentence Transformers: https://www.sbert.net/

**Code Parsing:**
- Python AST: https://docs.python.org/3/library/ast.html
- Tree-sitter: https://tree-sitter.github.io/tree-sitter/

**LLM APIs:**
- Claude API: https://docs.anthropic.com/
- OpenAI API: https://platform.openai.com/docs/

**UI Frameworks:**
- Streamlit: https://docs.streamlit.io/
- Gradio: https://www.gradio.app/docs/

---

## 🎤 ELEVATOR PITCH TEMPLATE

**30-Second Version:**
```
"Most AI coding assistants hallucinate and ignore your codebase patterns.

RepoPilot is different. It ingests your repository, understands your 
architecture, and grounds every answer in YOUR actual code.

When it doesn't have enough information? It refuses to guess - showing 
real engineering judgment.

It's not about generating more code. It's about generating the RIGHT code."
```

**2-Minute Version:**
```
[PROBLEM - 30 seconds]
"Developers waste hours understanding legacy codebases. Current AI assistants
don't help - they hallucinate, ignore patterns, and generate code that doesn't
match your architecture."

[SOLUTION - 30 seconds]
"RepoPilot solves this. It's a RAG-powered assistant that:
- Ingests your entire repository and builds a three-layer understanding
- Grounds every answer in your actual code - zero hallucination
- Detects and follows your patterns automatically
- Shows engineering judgment by refusing unsafe operations"

[DEMO - 45 seconds]
"Watch this. [Show repository ingestion → Ask question → Show confidence score
→ Ask risky question → Show smart refusal → Generate code → Show pattern matching]"

[IMPACT - 15 seconds]
"This isn't just a hackathon project. It's production-ready AI that thinks
like an engineer. Thank you."
```

---

## 📝 REQUIRED DELIVERABLES CHECKLIST

### Round 1 Submissions

**1. Documented Ingestion & Indexing Process** ✓
- [x] Code that loads repository
- [x] Chunking strategy explained
- [x] Embedding generation documented
- [x] Vector store setup detailed

**2. RAG-Grounded Q&A Demonstration** ✓
- [x] Minimum 5 developer queries answered
- [x] Sources shown for each answer
- [x] No hallucination (grounded only)

**3. Generated Code Examples** ✓
- [x] At least 3 code generation examples
- [x] Each with explanation of changes
- [x] Pattern alignment shown
- [x] Risk assessment included

**4. Generated PyTest Files** ✓
- [x] At least 2 test files generated
- [x] Match existing test style
- [x] Edge cases covered
- [x] Explanation of test strategy

**5. Design Document** ✓
Must include:
- [x] Agent architecture description
- [x] Data flow diagrams
- [x] Grounding strategy explained
- [x] Technologies used
- [x] Limitations documented

**6. Assumptions & Limitations List** ✓
- [x] Repository structure assumptions
- [x] Language support limitations
- [x] Confidence threshold explanations
- [x] Known edge cases

---

## 🎯 SUCCESS METRICS

### How to Measure Your Solution

**Retrieval Quality:**
```
Metric: Retrieval Precision @ 5
Target: > 80% of top 5 results relevant
How: Manual evaluation on 20 test queries
```

**Generation Accuracy:**
```
Metric: Pattern Compliance Rate
Target: > 90% generated code matches repo style
How: Run pattern checker on 10 generated snippets
```

**Confidence Calibration:**
```
Metric: Confidence-Accuracy Correlation
Target: High confidence (>80%) = High accuracy (>90%)
How: Compare confidence scores with manual correctness ratings
```

**Refusal Appropriateness:**
```
Metric: Precision of Refusals
Target: > 95% of refusals are justified
How: Review 20 refusal cases manually
```

**User Experience:**
```
Metric: Query → Answer Time
Target: < 5 seconds for simple queries
How: Time 20 sample queries
```

---

## 🔥 LAST-MINUTE POLISH TIPS

### If You Have Extra Time (Priority Order)

**1. Add Loading States** (15 minutes)
```python
with st.spinner("🔍 Searching repository..."):
    results = vector_store.search(query)
```

**2. Add Example Queries** (20 minutes)
```python
st.sidebar.markdown("### 💡 Example Queries")
examples = [
    "How does authentication work?",
    "Add caching to product search",
    "Explain the payment flow"
]
for ex in examples:
    if st.sidebar.button(ex):
        st.session_state["query"] = ex
```

**3. Add Error Handling** (30 minutes)
```python
try:
    results = vector_store.search(query)
except Exception as e:
    st.error(f"Search failed: {str(e)}")
    st.info("Try rephrasing your query")
```

**4. Add Copy-to-Clipboard** (10 minutes)
```python
st.code(generated_code, language="python")
st.button("📋 Copy Code")
```

**5. Add Dark Mode Toggle** (20 minutes)
```python
if st.sidebar.toggle("🌙 Dark Mode"):
    st.markdown("""<style>
        .main { background-color: #1e1e1e; }
    </style>""", unsafe_allow_html=True)
```

---

## 🎊 FINAL WORDS

### Your Winning Formula

```
RepoPilot = Deep Understanding + Safe Generation + Transparency

Deep Understanding:
  • Three-layer repository intelligence
  • Pattern detection and enforcement
  • Architectural awareness

Safe Generation:
  • Confidence scoring
  • Risk analysis
  • Smart refusal with explanations

Transparency:
  • Source attribution
  • Reasoning chains visible
  • "Show your work" mode
```

### The Pitch in One Sentence

**"RepoPilot is the only AI assistant that refuses to guess - it grounds every answer in your repository, respects your patterns, and shows real engineering judgment."**

---

## 📞 NEED HELP?

### Quick Debugging Guide

**Problem: Vector search returns irrelevant results**
```
Solution:
1. Check chunking strategy (functions > windows)
2. Lower similarity threshold (try 0.6 instead of 0.7)
3. Increase n_results (retrieve more, re-rank better)
```

**Problem: Code generation doesn't match style**
```
Solution:
1. Improve pattern detection (more examples)
2. Add explicit style constraints to prompt
3. Post-process with style checker
```

**Problem: Confidence scores always low**
```
Solution:
1. Adjust confidence calculation weights
2. Use better embedding model
3. Improve retrieval quality first
```

**Problem: Demo is slow**
```
Solution:
1. Pre-index repository before demo
2. Cache common queries
3. Use smaller test repository
```

---

## ✅ YOU'RE READY!

### Final Confidence Check

If you can answer YES to these:
- [ ] Can you ingest a repository in < 2 minutes?
- [ ] Can you answer 5 different types of queries?
- [ ] Can you show at least one smart refusal?
- [ ] Can you generate code that matches repo style?
- [ ] Can you explain every decision with sources?
- [ ] Is your UI clean and functional?
- [ ] Have you practiced the demo 3+ times?

**Then you're ready to WIN this hackathon! 🏆**

---

## 🚀 GO BUILD AND WIN!

Remember:
- Focus on the 9 core features
- Demo refusal (judges love this)
- Show confidence scores
- Practice the pitch
- Document everything

**You've got this! Now go build RepoPilot and show them what real repository intelligence looks like.**

---

*End of Guide - Good luck at the hackathon!* 🎉