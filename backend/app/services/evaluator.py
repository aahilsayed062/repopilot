"""
Feature 3: LLM vs LLM Evaluation Layer (Critic-Defender-Controller).

This module evaluates generated code with two independent reviewers and a
controller that produces a final decision:
- Critic: logic/correctness/security focus.
- Defender: robustness/style/testability focus.
- Controller: synthesizes both reviews into a final action.
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.utils.llm import llm
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReviewerVerdict(BaseModel):
    provider: str
    score: float
    issues: List[str] = Field(default_factory=list)
    feedback: str = ""
    suggested_changes: List[str] = Field(default_factory=list)


class ControllerVerdict(BaseModel):
    decision: str
    reasoning: str
    final_score: float
    confidence: float
    merged_issues: List[str] = Field(default_factory=list)
    priority_fixes: List[str] = Field(default_factory=list)
    improved_code_by_file: List[dict] = Field(default_factory=list)


class LLMVsLLMResult(BaseModel):
    enabled: bool = True
    critic: Optional[ReviewerVerdict] = None
    defender: Optional[ReviewerVerdict] = None
    controller: ControllerVerdict


class CodeEvaluator:
    MAX_CODE_BUNDLE_CHARS = 10_000
    MAX_FILE_CHARS = 2_200

    CRITIC_PROMPT = """You are the CRITIC reviewer.
You focus on correctness, logic bugs, security, and requirement fit.
Return valid JSON only.

User request:
{request_text}

Context:
{context}

Generated code:
{code_bundle}

Generated tests:
{tests_text}

Return JSON with this schema:
{{
  "score": 0-10 number,
  "issues": ["specific issue"],
  "feedback": "concise technical analysis",
  "suggested_changes": ["specific fix"]
}}"""

    DEFENDER_PROMPT = """You are the DEFENDER reviewer.
You focus on edge cases, robustness, style, maintainability, and testability.
Return valid JSON only.

User request:
{request_text}

Context:
{context}

Generated code:
{code_bundle}

Generated tests:
{tests_text}

Return JSON with this schema:
{{
  "score": 0-10 number,
  "issues": ["specific issue"],
  "feedback": "concise technical analysis",
  "suggested_changes": ["specific fix"]
}}"""

    CONTROLLER_PROMPT = """You are the CONTROLLER.
Synthesize two independent reviews into a final decision.
Return valid JSON only.

User request:
{request_text}

Generated code:
{code_bundle}

Critic review JSON:
{critic_json}

Defender review JSON:
{defender_json}

Decision rules:
- ACCEPT_ORIGINAL: code is good enough, only minor issues.
- REQUEST_REVISION: major correctness/security concerns.
- MERGE_FEEDBACK: acceptable but should apply concrete improvements.

Return JSON with this schema:
{{
  "decision": "ACCEPT_ORIGINAL|REQUEST_REVISION|MERGE_FEEDBACK",
  "reasoning": "why",
  "final_score": 0-10 number,
  "confidence": 0-1 number,
  "merged_issues": ["merged issue"],
  "priority_fixes": ["ordered high-impact fix"],
  "improved_code_by_file": [{{"file_path":"...", "code":"..."}}]
}}"""

    async def evaluate_generation(
        self,
        request_text: str,
        generated_diffs: List[dict],
        tests_text: str = "",
        context: str = "",
    ) -> LLMVsLLMResult:
        """Run full Critic-Defender-Controller evaluation."""
        code_bundle = self._build_code_bundle(generated_diffs)
        if not code_bundle.strip():
            return self._disabled_result("No generated diffs to evaluate.")

        critic_provider = "ollama"
        defender_provider = "gemini" if settings.gemini_api_key else "ollama_b"

        critic_task = self._run_reviewer(
            prompt_template=self.CRITIC_PROMPT,
            provider=critic_provider,
            request_text=request_text,
            code_bundle=code_bundle,
            tests_text=tests_text,
            context=context,
            reviewer_name="critic",
        )
        defender_task = self._run_reviewer(
            prompt_template=self.DEFENDER_PROMPT,
            provider=defender_provider,
            request_text=request_text,
            code_bundle=code_bundle,
            tests_text=tests_text,
            context=context,
            reviewer_name="defender",
        )

        critic_res, defender_res = await asyncio.gather(
            critic_task, defender_task, return_exceptions=True
        )

        critic = critic_res if isinstance(critic_res, ReviewerVerdict) else None
        defender = defender_res if isinstance(defender_res, ReviewerVerdict) else None

        if isinstance(critic_res, Exception):
            logger.error("critic_evaluation_failed", error=str(critic_res))
        if isinstance(defender_res, Exception):
            logger.error("defender_evaluation_failed", error=str(defender_res))

        controller = await self._run_controller(
            request_text=request_text,
            code_bundle=code_bundle,
            critic=critic,
            defender=defender,
        )

        return LLMVsLLMResult(
            enabled=True,
            critic=critic,
            defender=defender,
            controller=controller,
        )

    async def _run_reviewer(
        self,
        prompt_template: str,
        provider: str,
        request_text: str,
        code_bundle: str,
        tests_text: str,
        context: str,
        reviewer_name: str,
    ) -> ReviewerVerdict:
        tests_snippet = (tests_text or "").strip()
        if len(tests_snippet) > 2000:
            tests_snippet = tests_snippet[:2000] + "\n... [truncated]"

        prompt = prompt_template.format(
            request_text=request_text.strip(),
            context=(context or "None").strip()[:2000],
            code_bundle=code_bundle,
            tests_text=tests_snippet or "None",
        )

        response = await llm.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only. No markdown fences.",
                },
                {"role": "user", "content": prompt},
            ],
            json_mode=True,
            provider_override=provider,
            temperature=0.1,
            max_tokens=900,
        )
        data = self._parse_json_response(response)

        return ReviewerVerdict(
            provider=provider,
            score=self._normalize_score(data.get("score", 0.0)),
            issues=self._to_string_list(data.get("issues")),
            feedback=str(data.get("feedback", "")).strip(),
            suggested_changes=self._to_string_list(data.get("suggested_changes")),
        )

    async def _run_controller(
        self,
        request_text: str,
        code_bundle: str,
        critic: Optional[ReviewerVerdict],
        defender: Optional[ReviewerVerdict],
    ) -> ControllerVerdict:
        critic_json = json.dumps(critic.model_dump() if critic else {"error": "critic unavailable"})
        defender_json = json.dumps(defender.model_dump() if defender else {"error": "defender unavailable"})

        prompt = self.CONTROLLER_PROMPT.format(
            request_text=request_text.strip(),
            code_bundle=code_bundle,
            critic_json=critic_json,
            defender_json=defender_json,
        )

        try:
            response = await llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "Return valid JSON only. No markdown fences.",
                    },
                    {"role": "user", "content": prompt},
                ],
                json_mode=True,
                provider_override="ollama",
                temperature=0.1,
                max_tokens=900,
            )
            data = self._parse_json_response(response)
            decision = self._normalize_decision(str(data.get("decision", "")))

            improved_code = data.get("improved_code_by_file", [])
            if not isinstance(improved_code, list):
                improved_code = []

            return ControllerVerdict(
                decision=decision,
                reasoning=str(data.get("reasoning", "")).strip(),
                final_score=self._normalize_score(data.get("final_score", 0.0)),
                confidence=self._normalize_confidence(data.get("confidence", 0.0)),
                merged_issues=self._to_string_list(data.get("merged_issues")),
                priority_fixes=self._to_string_list(data.get("priority_fixes")),
                improved_code_by_file=[
                    item for item in improved_code if isinstance(item, dict)
                ],
            )
        except Exception as e:
            logger.error("controller_evaluation_failed", error=str(e))
            return self._fallback_controller(critic, defender)

    def _fallback_controller(
        self, critic: Optional[ReviewerVerdict], defender: Optional[ReviewerVerdict]
    ) -> ControllerVerdict:
        scores = [r.score for r in (critic, defender) if r is not None]
        final_score = sum(scores) / len(scores) if scores else 0.0
        decision = "ACCEPT_ORIGINAL" if final_score >= 7.5 else "REQUEST_REVISION"

        merged_issues: List[str] = []
        if critic:
            merged_issues.extend([f"[critic] {i}" for i in critic.issues])
        if defender:
            merged_issues.extend([f"[defender] {i}" for i in defender.issues])
        merged_issues = merged_issues[:12]

        if critic and defender:
            confidence = 0.85
        elif critic or defender:
            confidence = 0.6
        else:
            confidence = 0.2

        return ControllerVerdict(
            decision=decision,
            reasoning="Controller fallback used because controller evaluation failed.",
            final_score=round(final_score, 2),
            confidence=confidence,
            merged_issues=merged_issues,
            priority_fixes=merged_issues[:5],
            improved_code_by_file=[],
        )

    def _build_code_bundle(self, generated_diffs: List[dict]) -> str:
        parts: List[str] = []
        used = 0

        for change in generated_diffs or []:
            if not isinstance(change, dict):
                continue
            file_path = str(change.get("file_path", "unknown")).strip()
            body = (
                change.get("code")
                or change.get("content")
                or change.get("diff")
                or ""
            )
            text = str(body).strip()
            if not text:
                continue

            if len(text) > self.MAX_FILE_CHARS:
                text = text[: self.MAX_FILE_CHARS] + "\n... [truncated]"

            chunk = f"File: {file_path}\n{text}\n"
            remaining = self.MAX_CODE_BUNDLE_CHARS - used
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk[:remaining]
            parts.append(chunk)
            used += len(chunk)

        return "\n---\n".join(parts)

    def _disabled_result(self, reason: str) -> LLMVsLLMResult:
        return LLMVsLLMResult(
            enabled=False,
            critic=None,
            defender=None,
            controller=ControllerVerdict(
                decision="REQUEST_REVISION",
                reasoning=reason,
                final_score=0.0,
                confidence=0.0,
                merged_issues=[reason],
                priority_fixes=["Generate code diffs before evaluation."],
                improved_code_by_file=[],
            ),
        )

    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        clean = (text or "").strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.MULTILINE).strip()
        try:
            return json.loads(clean)
        except Exception:
            start = clean.find("{")
            end = clean.rfind("}")
            if start >= 0 and end > start:
                return json.loads(clean[start : end + 1])
            raise

    @staticmethod
    def _to_string_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        out: List[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return out

    @staticmethod
    def _normalize_score(score: Any) -> float:
        try:
            value = float(score)
        except Exception:
            value = 0.0
        return round(max(0.0, min(10.0, value)), 2)

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            conf = float(value)
        except Exception:
            conf = 0.0
        return round(max(0.0, min(1.0, conf)), 2)

    @staticmethod
    def _normalize_decision(decision: str) -> str:
        clean = (decision or "").strip().upper()
        if clean in {"ACCEPT_ORIGINAL", "REQUEST_REVISION", "MERGE_FEEDBACK"}:
            return clean
        return "REQUEST_REVISION"


evaluator = CodeEvaluator()

