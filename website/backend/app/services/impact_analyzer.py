"""
impact_analyzer.py - Risk & Change Impact Analysis (Feature 4).

Analyzes code changes to identify directly changed files, indirectly
affected files, risk level, and recommendations.
"""

import json
from typing import List, Optional
from pydantic import BaseModel, Field

from app.utils.logger import get_logger
from app.utils.llm import llm
from app.services.retriever import retriever

logger = get_logger(__name__)


class ImpactFile(BaseModel):
    file_path: str
    reason: str


class ImpactReport(BaseModel):
    directly_changed: List[str] = Field(default_factory=list)
    indirectly_affected: List[ImpactFile] = Field(default_factory=list)
    risk_level: str = "LOW"  # LOW | MEDIUM | HIGH | CRITICAL
    risks: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


IMPACT_SYSTEM_PROMPT = """You analyze code changes for risks. Given changed files and code, respond with JSON.

EXAMPLE — if someone changed `utils/auth.py`:
{"indirectly_affected": [{"file_path": "routes/login.py", "reason": "imports auth module"}], "risk_level": "MEDIUM", "risks": ["Changing auth logic may break login flow"], "recommendations": ["Test login and signup flows after this change"]}

RULES:
- risk_level must be exactly ONE of: LOW, MEDIUM, HIGH, CRITICAL
- risks and recommendations must be specific to these actual changes — NO generic placeholder text
- If the change is documentation-only, set risk_level to LOW
- NEVER output template text like "risk 1" or "recommendation 1"

Respond ONLY with valid JSON, no extra text."""


class ImpactAnalyzer:
    """Analyzes change impact using RAG retrieval + LLM reasoning."""

    async def analyze(
        self,
        code_changes: str,
        changed_files: List[str],
        repo_id: str,
    ) -> ImpactReport:
        logger.info(
            "impact_analysis_start",
            repo_id=repo_id,
            changed_files=changed_files,
        )

        if not changed_files:
            return ImpactReport(
                directly_changed=[],
                risk_level="LOW",
                risks=["No files changed"],
                recommendations=["Verify changes were applied correctly"],
            )

        # 1. Find related files via retrieval
        related_context = ""
        for file_path in changed_files[:3]:  # Limit to avoid overloading
            try:
                query = f"files that import or reference {file_path}"
                chunks = await retriever.retrieve(repo_id, query, k=2)
                for chunk in chunks:
                    if chunk.metadata.file_path not in changed_files:
                        related_context += (
                            f"\n--- {chunk.metadata.file_path} ---\n"
                            f"{chunk.content[:400]}\n"
                        )
            except Exception as e:
                logger.warning("retrieval_failed_for_impact", file=file_path, error=str(e))

        # 2. Build LLM prompt
        messages = [
            {"role": "system", "content": IMPACT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Changed files: {', '.join(changed_files)}\n\n"
                    f"Code changes:\n{code_changes[:1200]}\n\n"
                    f"Related repository files:\n{related_context[:800]}"
                ),
            },
        ]

        try:
            response_text = await llm.chat_completion(
                messages, json_mode=True, max_tokens=512
            )
            clean_text = response_text.strip()
            if clean_text.startswith("```"):
                import re
                clean_text = re.sub(
                    r"^```(?:json)?\s*|\s*```$", "", clean_text, flags=re.MULTILINE
                )
            clean_text = clean_text.strip()
            if not clean_text.startswith("{"):
                clean_text = f"{{{clean_text}}}"

            data = json.loads(clean_text)

            indirectly_affected = []
            for item in data.get("indirectly_affected", []):
                if isinstance(item, dict):
                    indirectly_affected.append(
                        ImpactFile(
                            file_path=item.get("file_path", "unknown"),
                            reason=item.get("reason", ""),
                        )
                    )
                elif isinstance(item, str):
                    indirectly_affected.append(
                        ImpactFile(file_path=item, reason="referenced")
                    )

            return ImpactReport(
                directly_changed=changed_files,
                indirectly_affected=indirectly_affected,
                risk_level=data.get("risk_level", "MEDIUM").upper(),
                risks=data.get("risks", []),
                recommendations=data.get("recommendations", []),
            )

        except Exception as e:
            logger.exception("impact_analysis_failed", error=str(e))
            # Return a safe fallback
            return ImpactReport(
                directly_changed=changed_files,
                risk_level="MEDIUM",
                risks=["Impact analysis encountered an error — review changes manually"],
                recommendations=["Check imports and dependencies of changed files"],
            )


# Singleton
impact_analyzer = ImpactAnalyzer()
