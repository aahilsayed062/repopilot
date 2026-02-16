"""
Answerer Service - Generates grounded answers from retrieved chunks.
"""

import json
import re
from typing import List

from app.utils.logger import get_logger
from app.utils.llm import llm
from app.models.chunk import Chunk
from app.models.chat import ChatResponse, AnswerConfidence

logger = get_logger(__name__)


def _clean_answer_text(text: str) -> str:
    """Strip any JSON metadata that leaked into the answer text."""
    if not isinstance(text, str):
        return str(text)
    text = text.strip()
    
    # Remove JSON opening patterns like {"answer": or { "answer":
    text = re.sub(r'^\s*\{\s*"?answer"?\s*:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*\{\s*$', '', text, flags=re.MULTILINE)
    
    # If answer starts with JSON, extract the real answer
    if text.startswith('{') and '"answer"' in text:
        match = re.search(r'"answer"\s*:\s*"(.*?)(?<!\\)"', text, re.DOTALL)
        if match:
            try:
                text = match.group(1).encode('utf-8').decode('unicode_escape')
            except Exception:
                text = match.group(1)
    
    # Remove JSON metadata patterns that leak into answer
    text = re.sub(r'\s*,?\s*\n?\s*"?citations"?\s*:.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\s*,?\s*\n?\s*"?confidence"?\s*:.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\s*,?\s*\n?\s*"?assumptions"?\s*:.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up trailing/leading commas, braces and whitespace
    text = re.sub(r'^\s*[{,]\s*', '', text)
    text = re.sub(r'\s*[},]\s*$', '', text)
    text = text.strip()
    
    return text


class Answerer:
    """
    Generates structured answers grounded in retrieved repository chunks.
    """

    MAX_CONTENT_LENGTH = 800
    MAX_CITATIONS = 3

    SYSTEM_PROMPT = """You are RepoPilot, a code assistant that answers questions about repositories.

Rules:
1. Use ONLY the provided source code context to answer. Cite sources as [S1], [S2], etc.
2. If the code context is not enough, say so honestly.
3. Be direct, technical, and helpful.

Always respond with this JSON format:
{"answer": "your answer here using markdown", "confidence": "high or medium or low", "citations": [{"file_path": "file.py", "line_range": "L1-L50", "why": "reason"}]}
"""

    SYSTEM_PROMPT_STREAM = """Answer using ONLY the provided code context. Cite sources as [S1], [S2]. Use Markdown."""

    TEMPLATE_LEAK_MARKERS = (
        "markdown with sections",
        "short answer, ## evidence from code, ## practical next step",
        "return valid json with this exact schema",
    )

    GENERIC_NONANSWER_MARKERS = (
        "review the code for any potential",
        "ensure user input is properly validated",
        "consider using more robust typing",
        "could lead to potential issues",
        "potential vulnerabilities",
    )

    def _generate_citations_from_chunks(self, chunks: List[Chunk]) -> List[dict]:
        """Generate deterministic citations from retrieved chunks."""
        citations = []
        for chunk in chunks[: self.MAX_CITATIONS]:
            snippet = chunk.content.strip().replace("\n", " ")
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."
            citations.append(
                {
                    "file_path": chunk.file_path,
                    "line_range": chunk.line_range,
                    "snippet": snippet,
                    "why": "Retrieved as relevant repository evidence.",
                }
            )
        return citations

    def _parse_response(self, response_text: str) -> dict:
        """Parse LLM response into structured data."""
        clean_text = response_text.strip()

        if clean_text.startswith("```"):
            clean_text = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", clean_text, flags=re.MULTILINE
            ).strip()

        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            pass

        if not clean_text.startswith("{"):
            try:
                return json.loads(f"{{{clean_text}}}")
            except json.JSONDecodeError:
                pass

        match = re.search(r'"answer"\s*:\s*"(.*?)(?<!\\)"', clean_text, re.DOTALL)
        if match:
            try:
                answer = match.group(1).encode("utf-8").decode("unicode_escape")
            except Exception:
                answer = match.group(1)

            conf_match = re.search(
                r'"confidence"\s*:\s*"?(high|medium|low)"?', clean_text, re.IGNORECASE
            )
            confidence = conf_match.group(1).lower() if conf_match else "medium"

            return {
                "answer": answer,
                "citations": [],
                "confidence": confidence,
                "assumptions": [],
            }
        return {}

    def _normalize_line_range(self, line_range: str) -> str:
        """Normalize line ranges to Lx-Ly format."""
        if not isinstance(line_range, str):
            return ""
        cleaned = line_range.strip().upper().replace(" ", "")
        cleaned = cleaned.replace("LINES", "L").replace("LINE", "L")
        if re.match(r"^L\d+-L\d+$", cleaned):
            return cleaned
        if re.match(r"^L\d+$", cleaned):
            return f"{cleaned}-{cleaned}"
        return line_range.strip()

    def _validate_citations(self, raw_citations: List[dict], chunks: List[Chunk]) -> List[dict]:
        """Keep only citations that match retrieved chunks."""
        chunk_map = {(c.file_path, c.line_range): c for c in chunks}
        first_by_file = {}
        for chunk in chunks:
            first_by_file.setdefault(chunk.file_path, chunk)

        valid: List[dict] = []
        seen = set()

        for cit in raw_citations or []:
            if not isinstance(cit, dict):
                continue
            file_path = str(cit.get("file_path", "")).strip()
            line_range = self._normalize_line_range(str(cit.get("line_range", "")).strip())

            matched_chunk = chunk_map.get((file_path, line_range))
            if not matched_chunk and file_path in first_by_file:
                matched_chunk = first_by_file[file_path]
                line_range = matched_chunk.line_range

            if not matched_chunk:
                continue

            key = (matched_chunk.file_path, line_range)
            if key in seen:
                continue
            seen.add(key)

            snippet = str(cit.get("snippet", "")).strip()
            if not snippet:
                snippet = matched_chunk.content.strip().replace("\n", " ")
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."

            why = str(cit.get("why", "")).strip() or "Supports the answer."
            valid.append(
                {
                    "file_path": matched_chunk.file_path,
                    "line_range": line_range,
                    "snippet": snippet,
                    "why": why,
                }
            )

        return valid[: self.MAX_CITATIONS]

    def _estimate_confidence(
        self,
        answer_text: str,
        chunks: List[Chunk],
        citations: List[dict],
        assumptions: List[str],
        llm_confidence: str,
    ) -> AnswerConfidence:
        """Compute confidence from evidence coverage, then calibrate downward if needed."""
        if not chunks or not citations:
            return AnswerConfidence.LOW

        lowered_answer = answer_text.lower()
        if self._is_placeholder_answer(answer_text) or self._looks_generic_non_answer(answer_text):
            return AnswerConfidence.LOW

        uncertainty_markers = [
            "insufficient evidence",
            "not enough context",
            "cannot determine",
            "unable to verify",
            "not present in the provided context",
            "no information provided",
            "no files defining",
        ]
        if any(marker in lowered_answer for marker in uncertainty_markers):
            return AnswerConfidence.LOW

        cited_unique = len({(c["file_path"], c["line_range"]) for c in citations})
        if cited_unique >= 3:
            score = 2
        elif cited_unique >= 2:
            score = 1
        else:
            score = 0

        llm_conf = str(llm_confidence or "").lower().strip()
        if llm_conf == "high":
            score = max(score, 2)
        elif llm_conf == "medium":
            score = max(score, 1)

        # If the answer does not reference source ids, cap confidence at medium.
        if "[s1]" not in lowered_answer and "[s2]" not in lowered_answer:
            score = min(score, 1)

        if assumptions:
            score = max(0, score - 1)

        if score >= 2:
            return AnswerConfidence.HIGH
        if score == 1:
            return AnswerConfidence.MEDIUM
        return AnswerConfidence.LOW

    def _is_placeholder_answer(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return True
        return any(marker in lowered for marker in self.TEMPLATE_LEAK_MARKERS)

    def _looks_generic_non_answer(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return True
        generic_hits = sum(1 for marker in self.GENERIC_NONANSWER_MARKERS if marker in lowered)
        return generic_hits >= 2

    async def _retry_for_concrete_answer(self, messages: List[dict], query: str) -> dict:
        retry_messages = messages + [
            {
                "role": "user",
                "content": (
                    "Your previous output was template-like or too generic. "
                    "Retry with a concrete, repository-grounded answer for this exact question: "
                    f"{query}\n"
                    "Return valid JSON only."
                ),
            }
        ]
        retry_text = await llm.chat_completion(retry_messages, json_mode=True)
        return self._parse_response(retry_text) or {}

    def _ensure_structured_answer(
        self, answer_text: str, citations: List[dict], assumptions: List[str]
    ) -> str:
        """Guarantee a structured answer format even on fallback paths."""
        text = answer_text.strip()
        if self._is_placeholder_answer(text):
            text = ""

        text = re.sub(
            r"(?im)^#\s*(Direct Answer|Answer|Short Answer)\s*$",
            "## Short Answer",
            text,
        )
        text = re.sub(
            r"(?im)^#\s*(Evidence|Evidence From Code|Why This Is True)\s*$",
            "## Evidence From Code",
            text,
        )
        text = re.sub(
            r"(?im)^#\s*(Next Steps|Practical Next Step|Recommended Next Step)\s*$",
            "## Practical Next Step",
            text,
        )
        text = re.sub(
            r"(?im)^##\s*(Direct Answer|Answer)\s*$",
            "## Short Answer",
            text,
        )
        text = re.sub(
            r"(?im)^##\s*(Evidence|Why This Is True)\s*$",
            "## Evidence From Code",
            text,
        )
        text = re.sub(
            r"(?im)^##\s*(Next Steps|Recommended Next Step)\s*$",
            "## Practical Next Step",
            text,
        )

        has_direct = "## short answer" in text.lower()
        has_evidence = "## evidence from code" in text.lower()
        has_next_steps = "## practical next step" in text.lower()

        if has_direct and has_evidence and has_next_steps:
            return text

        direct = text or "I couldn't ground this confidently in the current context."
        evidence_lines = []
        for idx, cit in enumerate(citations[: self.MAX_CITATIONS], start=1):
            location = f"`{cit['file_path']}:{cit['line_range']}`"
            reason = cit.get("why", "").strip() or "Relevant repository evidence."
            evidence_lines.append(f"- [S{idx}] {location} - {reason}")

        if not evidence_lines:
            evidence_lines = ["- No validated citations were available."]

        next_steps = ["- Ask a narrower question with a file path, symbol, or module name."]
        if assumptions:
            next_steps.append("- Review the listed assumptions before applying this answer.")

        return (
            "## Short Answer\n"
            f"{direct}\n\n"
            "## Evidence From Code\n"
            f"{chr(10).join(evidence_lines)}\n\n"
            "## Practical Next Step\n"
            f"{chr(10).join(next_steps)}"
        )

    async def answer(
        self,
        query: str,
        chunks: List[Chunk],
        conversation_context: str = "",
    ) -> ChatResponse:
        """
        Generate an answer grounded in retrieved chunks.
        """
        if not chunks:
            return ChatResponse(
                answer=(
                    "## Short Answer\n"
                    "I don't have enough repository evidence yet to answer this safely.\n\n"
                    "## Evidence From Code\n"
                    "- No repository chunks matched the question.\n\n"
                    "## Practical Next Step\n"
                    "- Re-index the repository.\n"
                    "- Ask with a file path, module, or symbol name so I can anchor to exact code."
                ),
                citations=[],
                confidence=AnswerConfidence.LOW,
                assumptions=["No relevant repository context retrieved."],
            )

        context_parts = []
        for i, chunk in enumerate(chunks[: self.MAX_CITATIONS], start=1):
            source_id = f"S{i}"
            content = chunk.content
            if len(content) > self.MAX_CONTENT_LENGTH:
                content = content[: self.MAX_CONTENT_LENGTH] + "... [truncated]"

            context_parts.append(
                f"[{source_id}]\n"
                f"File: {chunk.file_path}\n"
                f"Lines: {chunk.line_range}\n"
                f"Content:\n{content}\n"
            )

        context_str = "\n---\n".join(context_parts)
        user_prompt = f"Context:\n{context_str}\n\nQuestion: {query}"
        if conversation_context:
            user_prompt = (
                f"Context:\n{context_str}\n\n"
                f"Recent conversation context:\n{conversation_context}\n\n"
                f"Question: {query}"
            )
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response_text = await llm.chat_completion(messages, json_mode=True)
            data = self._parse_response(response_text) or {}

            raw_answer = _clean_answer_text(data.get("answer", "") or "")
            raw_assumptions = data.get("assumptions", [])
            assumptions = [
                str(item).strip()
                for item in (raw_assumptions if isinstance(raw_assumptions, list) else [])
                if str(item).strip()
            ]

            # Skip quality retry to conserve API quota (was doubling LLM calls)
            if self._is_placeholder_answer(raw_answer):
                logger.warning("answer_quality_low", answer_preview=raw_answer[:80])

            validated_citations = self._validate_citations(data.get("citations", []), chunks)
            if not validated_citations:
                validated_citations = self._generate_citations_from_chunks(chunks)
                logger.info("injected_fallback_citations", count=len(validated_citations))

            structured_answer = self._ensure_structured_answer(
                raw_answer, validated_citations, assumptions
            )
            confidence = self._estimate_confidence(
                structured_answer,
                chunks,
                validated_citations,
                assumptions,
                str(data.get("confidence", "")).lower(),
            )
            final_assumptions = assumptions if confidence == AnswerConfidence.LOW else []

            return ChatResponse(
                answer=structured_answer,
                citations=validated_citations,
                confidence=confidence,
                assumptions=final_assumptions,
            )

        except Exception as e:
            logger.error("answer_generation_failed", error=str(e))
            error_citations = self._generate_citations_from_chunks(chunks) if chunks else []
            return ChatResponse(
                answer=(
                    "## Short Answer\n"
                    "I hit an internal error while generating your grounded answer.\n\n"
                    "## Evidence From Code\n"
                    "- The response pipeline failed before final formatting.\n\n"
                    "## Practical Next Step\n"
                    "- Retry the question.\n"
                    "- If this repeats, re-index the repository and check backend logs."
                ),
                citations=error_citations,
                confidence=AnswerConfidence.LOW,
                assumptions=[str(e)],
            )

    async def answer_stream(
        self,
        query: str,
        chunks: List[Chunk],
        conversation_context: str = "",
    ):
        """
        Stream an answer grounded in retrieved chunks.
        """
        context_parts = []
        for i, chunk in enumerate(chunks[: self.MAX_CITATIONS], start=1):
            source_id = f"S{i}"
            content = chunk.content
            if len(content) > self.MAX_CONTENT_LENGTH:
                content = content[: self.MAX_CONTENT_LENGTH] + "... [truncated]"

            context_parts.append(
                f"[{source_id}]\n"
                f"File: {chunk.file_path}\n"
                f"Lines: {chunk.line_range}\n"
                f"Content:\n{content}\n"
            )

        context_str = "\n---\n".join(context_parts)
        user_prompt = f"Context:\n{context_str}\n\nQuestion: {query}"
        if conversation_context:
            user_prompt = (
                f"Context:\n{context_str}\n\n"
                f"Recent conversation context:\n{conversation_context}\n\n"
                f"Question: {query}"
            )
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT_STREAM},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # First, check if there are no chunks
            if not chunks:
                yield "I don't have enough repository evidence yet to answer this safely.\n\n"
                yield "- No repository chunks matched the question.\n"
                yield "- Try re-indexing or asking with a specific file path."
                return

            async for chunk in llm.chat_completion_stream(messages, json_mode=False):
                yield chunk
                
        except Exception as e:
            logger.error("answer_stream_failed", error=str(e))
            yield f"\n[Error: {str(e)}]"


# Global instance
answerer = Answerer()
