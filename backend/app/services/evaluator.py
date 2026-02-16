"""
Feature 3: LLM vs LLM Evaluation Layer.

Uses two independent Ollama models to review generated code:
- Model A (Primary): Deep correctness & logic check.
- Model B (Reviewer): Quick style, safety, and edge-case check.

The system merges their feedback to score the code (0-10) and suggest improvements.
"""

import asyncio
import json
from typing import List, Optional
from pydantic import BaseModel
from app.utils.llm import llm
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EvaluationResult(BaseModel):
    score: float  # 0.0 to 10.0
    feedback: str
    issues: List[str]
    confidence: float


class CodeEvaluator:
    # -------------------------------------------------------------------------
    # Prompts
    # -------------------------------------------------------------------------
    
    # Model A Prompt (Detailed Logic Check)
    PROMPT_MODEL_A = """You are a Senior Code Reviewer (Agent A).
Analyze the provided code for LOGIC, CORRECTNESS, and SECURITY.

Context: {context}

Code to review:
```
{code}
```

Task:
1. Identify logic errors or bugs.
2. Check for security vulnerabilities.
3. Verify it solves the user's request.

Return JSON:
{{
  "score": <0-10, be strict>,
  "issues": ["critical bug...", "logic error..."],
  "feedback": "Detailed technical feedback."
}}"""

    # Model B Prompt (Style & Edge Cases)
    PROMPT_MODEL_B = """You are a QA Reviewer (Agent B).
Analyze the provided code for STYLE, EDGE CASES, and ROBUSTNESS.

Context: {context}

Code to review:
```
{code}
```

Task:
1. Check for missing edge cases (empty inputs, nulls).
2. Check code style and PEP8/linting.
3. Check exception handling.

Return JSON:
{{
  "score": <0-10, be strict>,
  "issues": ["missing error handling...", "style issue..."],
  "feedback": "Quick observations."
}}"""

    async def evaluate(self, code: str, context: str = "") -> EvaluationResult:
        """
        Run parallel evaluation using two LLM models.
        """
        logger.info("starting_evaluation", context_len=len(context), code_len=len(code))

        # Run both models in parallel
        # Model A: Primary (3b) -> provider="ollama"
        # Model B: Reviewer (1.5b) -> provider="ollama_b"
        task_a = self._get_review(
            self.PROMPT_MODEL_A, code, context, provider="ollama", model_name="Model A"
        )
        task_b = self._get_review(
            self.PROMPT_MODEL_B, code, context, provider="ollama_b", model_name="Model B"
        )

        results = await asyncio.gather(task_a, task_b, return_exceptions=True)
        
        # Process results
        res_a = results[0] if not isinstance(results[0], Exception) else None
        res_b = results[1] if not isinstance(results[1], Exception) else None

        if isinstance(results[0], Exception):
            logger.error("evaluator_model_a_failed", error=str(results[0]))
        if isinstance(results[1], Exception):
            logger.error("evaluator_model_b_failed", error=str(results[1]))

        return self._merge_reviews(res_a, res_b)

    async def _get_review(
        self, prompt_template: str, code: str, context: str, provider: str, model_name: str
    ) -> Optional[dict]:
        """Call a specific LLM model to get a review."""
        prompt = prompt_template.format(code=code, context=context)
        messages = [{"role": "user", "content": prompt}]
        
        try:
            # provider_override forces the specific Ollama model
            response = await llm.chat_completion(
                messages, 
                json_mode=True, 
                provider_override=provider,
                temperature=0.2  # Low temp for consistent reviews
            )
            return json.loads(response)
        except Exception as e:
            logger.error(f"evaluator_{model_name.lower().replace(' ', '_')}_failed", error=str(e))
            return None

    def _merge_reviews(self, res_a: Optional[dict], res_b: Optional[dict]) -> EvaluationResult:
        """Merge feedback from both models into a final result."""
        
        # Defaults
        score_a = res_a.get("score", 5.0) if res_a else 0.0
        score_b = res_b.get("score", 5.0) if res_b else 0.0
        
        issues = []
        feedback_parts = []
        
        if res_a:
            issues.extend([f"[Logic] {i}" for i in res_a.get("issues", [])])
            feedback_parts.append(f"**Logic Review:** {res_a.get('feedback', '')}")
            
        if res_b:
            issues.extend([f"[QA] {i}" for i in res_b.get("issues", [])])
            feedback_parts.append(f"**QA Review:** {res_b.get('feedback', '')}")

        if not res_a and not res_b:
            return EvaluationResult(
                score=0.0,
                feedback="Evaluation failed for both models.",
                issues=["Internal evaluation error"],
                confidence=0.0
            )

        # Weighted score: Logic (A) is 60%, QA (B) is 40%
        if res_a and res_b:
            final_score = (score_a * 0.6) + (score_b * 0.4)
            confidence = 0.9
        elif res_a:
            final_score = score_a
            confidence = 0.6  # Only one model ran
            feedback_parts.append("(Note: QA model failed to run)")
        else:
            final_score = score_b
            confidence = 0.4  # Only the smaller model ran
            feedback_parts.append("(Note: Primary logic model failed to run)")

        return EvaluationResult(
            score=round(final_score, 1),
            feedback="\n\n".join(feedback_parts),
            issues=issues,
            confidence=confidence
        )


evaluator = CodeEvaluator()
