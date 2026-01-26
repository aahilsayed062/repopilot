# RepoPilot AI - Assumptions & Limitations

## Repository Assumptions

1. **Language Support**: Best results with Python, JavaScript/TypeScript, and Markdown. Other languages are indexed but may have lower accuracy.
2. **File Size**: Files larger than 1MB are skipped to avoid memory issues.
3. **Encoding**: All files assumed to be UTF-8 encoded.
4. **Structure**: Standard project structure expected (src/, tests/, README.md, etc.).

## Build/Test Assumptions

1. **No Execution**: Round 1 does NOT execute code. All analysis is static.
2. **No Dependency Resolution**: Import statements are indexed but not resolved to external packages.
3. **Test Generation**: Generated tests are for human review; they are not auto-run.

## Environment Assumptions

1. **LLM Provider**: Groq free tier (12k TPM limit). May hit rate limits on large queries.
2. **Embeddings**: Using mock embeddings (random vectors) unless OpenAI/Gemini key provided.
3. **Storage**: Local ChromaDB; not production-ready for multi-user.

## Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Mock embeddings | Retrieval quality is random | Use real embedding API for production |
| Rate limits (Groq) | Large context queries fail | Reduced `top_k` to 3 |
| No code execution | Cannot verify generated code | Manual review required |
| Single repo at a time | No cross-repo analysis | Scope limitation for Round 1 |
| No incremental indexing | Full re-index on changes | Future enhancement |

## Constraints Policy

- **Grounding**: All answers cite source files or explicitly state "general knowledge".
- **Hallucination Control**: If confidence is `low`, the system warns the user.
- **External Knowledge**: Only used for auxiliary tooling (e.g., LLM API). Core answers come from repo.
