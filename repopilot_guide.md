1. Executive Definition — What RepoPilot AI Actually Is

RepoPilot AI is a Repository-Grounded Engineering Intelligence System.

Its purpose is not to generate code blindly.

Its purpose is to:

• Understand a GitHub repository deeply
• Answer engineering questions grounded only in that repository
• Generate new code aligned with repository patterns
• Explain reasoning, risks, and assumptions
• Refuse unsafe or unsupported operations

The system must operate under this absolute constraint:

The repository is the only source of truth.

No hallucination. No guessing.

As defined in the PS:

Build a multi-agent RAG system that ingests a GitHub repository and acts as a repository-grounded engineering assistant prioritizing deep understanding, cautious generation, and explainability.

2. The Core Problem RepoPilot Solves

Real-world repositories are complex systems.

They contain:

• thousands of files
• evolving architecture
• hidden dependencies
• inconsistent patterns
• undocumented assumptions

Normal AI assistants fail because they:

• hallucinate patterns
• ignore repository architecture
• generate unsafe code
• cannot explain decisions

RepoPilot solves this by grounding intelligence in repository reality.

3. Core Functional Objective (Primary System Mission)

RepoPilot must build these five fundamental capabilities:

Capability 1: Repository Ingestion & Indexing

This is the foundation layer.

The system must:

Parse repository structure:

• files
• folders
• modules
• dependencies
• imports
• configs
• documentation

Extract:

• file hierarchy
• code content
• function definitions
• class definitions
• import relationships

Output internal intelligence model:

Repository Intelligence Model


This becomes the system’s memory.

Capability 2: Repository-Grounded Question Answering (RAG)

This is the reasoning layer.

When user asks:

"How authentication works?"

System must:

Step 1 — retrieve relevant repository files
Step 2 — analyze code
Step 3 — synthesize explanation
Step 4 — cite source files

It must never use external assumptions.

Every answer must be traceable to repository files.

Capability 3: Query Decomposition

This is cognitive planning.

Complex queries must be broken down.

Example query:

"Add caching to checkout and write tests"

System must split into:

1 Understand checkout system
2 Check caching pattern existence
3 Generate caching logic
4 Generate test cases

This simulates engineer reasoning.

Capability 4: Repository-Aligned Code Generation

This is constrained generation.

System must generate code that follows repository patterns:

• naming conventions
• architecture structure
• dependency patterns
• coding style
• module boundaries

If repository uses snake_case → generate snake_case
If repository uses MVC → follow MVC

Never introduce alien patterns.

Capability 5: Explainability Engine

This is transparency layer.

System must explain:

• which files were used
• why generation decision was made
• what assumptions exist
• what risks exist
• what information is missing

This builds trust.

Capability 6: Safe Refusal System (Critical Requirement)

This is the most important differentiator.

If insufficient information exists:

System must refuse.

Example:

User asks:

"Add payment system"

If repository has no payment structure:

System must respond:

"Cannot proceed safely due to missing repository context"

This proves engineering responsibility.

4. Architectural Model (Actual System Design)

RepoPilot consists of 6 core subsystems:

Subsystem 1: Repository Intelligence Engine

Input:

GitHub repository

Output:

Structured intelligence model

Includes:

• file tree
• imports graph
• functions index
• modules index

Subsystem 2: Vector Store (Semantic Memory)

Purpose:

Enable semantic retrieval

Process:

• split files into chunks
• convert chunks to embeddings
• store in vector database

Tools:

ChromaDB / FAISS

Subsystem 3: Query Processor

Purpose:

Understand user query

Extract:

• intent
• entities
• complexity

Example:

Intent: generate
Target: authentication module

Subsystem 4: Retrieval Engine

Purpose:

Find relevant repository code

Input:

query

Output:

relevant file chunks

Subsystem 5: Decision Router

Purpose:

Decide system action:

Possible actions:

• EXPLAIN
• GENERATE
• REFUSE

Based on:

• confidence score
• pattern clarity
• risk level

Subsystem 6: Code Generator

Purpose:

Generate repository-aligned code

Constraints:

• follow naming conventions
• follow structure
• follow style

5. Required Features (Mandatory Implementation Requirements)

These are non-negotiable deliverables:

Feature 1: Repository-Aware Q&A

User must be able to ask:

"What does login function do?"

System must answer grounded in repo files.

Feature 2: Automatic Query Decomposition

Complex query must be broken into smaller tasks.

Feature 3: Pattern-Aware Code Generation

Generated code must match repository patterns.

Feature 4: PyTest Generation

System must generate test cases aligned with repo style.

Feature 5: Pattern Consistency Analysis

System must detect conflicting coding styles.

Example:

snake_case vs camelCase conflict.

Feature 6: Safe Refusal

System must refuse when unsafe.

6. Core Constraint Model (Critical Hackathon Constraint)

Round 1 constraint:

Only reasoning allowed.

No automatic execution required.

Round 2 allows execution and refinement.

7. Operational Flow (Complete System Lifecycle)

Complete pipeline:

User → Query Processor → Retrieval Engine → Decision Router → Generator / Explanation → Output

8. Engineering Philosophy (Deep Meaning of RepoPilot)

RepoPilot is not designed to be:

• code generator
• chatbot
• autocomplete system

RepoPilot is designed to be:

Repository intelligence system.

It builds:

Structural awareness
Semantic awareness
Architectural awareness

This simulates engineer cognition.

9. Evaluation Criteria (What Judges Actually Measure)

Judges evaluate:

Repository understanding depth
Grounded reasoning quality
Pattern compliance
Explainability
Refusal correctness
Architecture clarity

Not code quantity.

10. What You Are Actually Building (True System Identity)

RepoPilot is fundamentally:

A repository-specific engineering intelligence layer.

In real-world analogy:

ChatGPT = general intelligence
RepoPilot = company-specific engineering intelligence

11. Minimal Required Working Version (What you MUST ensure tomorrow)

These must work:

Repository ingestion
Query answering grounded in repo
Confidence display
Code generation
Safe refusal
Basic UI

Everything else optional.

12. How Antigravity Should Think While Working

Antigravity must treat RepoPilot as 4-stage system:

Stage 1 — Build memory (vector store)

Stage 2 — Build retrieval engine

Stage 3 — Build reasoning router

Stage 4 — Build controlled generator