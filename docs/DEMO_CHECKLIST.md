# Demo Checklist (PS7)

## Pre-Demo Setup

1. Start backend on `:8000`
2. Start frontend on `:3000`
3. Open web UI and confirm backend health indicator

## Demo Flow

1. Repository ingestion
- Paste GitHub repository URL
- Click connect and show loading progress

2. Indexing
- Trigger indexing and show progress percentage
- Confirm chunk count appears when complete

3. Grounded Q&A
- Ask architecture or flow question
- Highlight structured answer + citations + confidence

4. Query decomposition
- Ask a complex multi-part question
- Show synthesized answer from sub-query retrieval

5. Code generation
- Use `/generate ...` request
- Show returned plan and diffs

6. PyTest generation
- Call PyTest generation path
- Show generated tests artifact

7. Safe refusal
- Ask for missing/non-existent module in repo
- Show low-confidence refusal with assumptions

## Evidence to Capture

- Screenshots of progress and grounded response cards
- Sample API response JSON for `/chat/ask`
- Sample code-generation and pytest outputs

## Talking Points

- Repository is source of truth
- Retrieval-first grounding reduces hallucinations
- Explainability comes from citations + confidence + assumptions
- Performance tuned for practical indexing latency
