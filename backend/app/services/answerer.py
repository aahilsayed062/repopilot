"""
Answerer Service - Generates grounded answers from retrieved chunks.
"""

import json
import re
from typing import List

from app.utils.logger import get_logger
from app.utils.llm import llm
from app.models.chunk import Chunk
from app.models.chat import ChatResponse, Citation, AnswerConfidence

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
    Generates answers using LLM and retrieved context.
    """
    
    # Limit per-chunk content to avoid token overflow
    MAX_CONTENT_LENGTH = 600
    
    SYSTEM_PROMPT = """You are RepoPilot, a helpful engineering assistant that answers questions about codebases.

Rules:
1. If you have context from the codebase, use it to answer accurately.
2. ALWAYS cite your sources with file_path and line_range from the context.
3. If no relevant context is found, provide helpful general information and set confidence to "low".
4. Be concise and actionable.

IMPORTANT: Return your response as a JSON object with this exact structure:
{
    "answer": "Your answer here as plain markdown text. Do NOT include JSON in this field.",
    "citations": [
        {"file_path": "path/to/file", "line_range": "L10-L20", "snippet": "relevant code", "why": "reason this is relevant"}
    ],
    "confidence": "high" or "medium" or "low",
    "assumptions": ["any assumptions made"]
}

CRITICAL: You MUST include citations for every source you reference. If you mention code from the context, cite it!
"""
    
    def _generate_citations_from_chunks(self, chunks: List[Chunk]) -> List[dict]:
        """Generate citation dicts from chunks as fallback."""
        citations = []
        for chunk in chunks[:5]:  # Limit to top 5
            citations.append({
                "file_path": chunk.file_path,
                "line_range": chunk.line_range,
                "snippet": chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content,
                "why": "Retrieved as relevant context"
            })
        return citations
    
    def _parse_response(self, response_text: str) -> dict:
        """Parse LLM response into structured data."""
        clean_text = response_text.strip()
        
        # Remove markdown code blocks if present
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean_text, flags=re.MULTILINE)
            clean_text = clean_text.strip()
        
        # Strategy 1: Direct JSON parse
        try:
            data = json.loads(clean_text)
            return data
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Fix missing braces
        if not clean_text.startswith("{"):
            try:
                data = json.loads(f"{{{clean_text}}}")
                return data
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Regex extraction
        match = re.search(r'"answer"\s*:\s*"(.*?)(?<!\\)"', clean_text, re.DOTALL)
        if match:
            try:
                answer = match.group(1).encode('utf-8').decode('unicode_escape')
            except Exception:
                answer = match.group(1)
            
            # Try to extract confidence too
            conf_match = re.search(r'"confidence"\s*:\s*"?(high|medium|low)"?', clean_text, re.IGNORECASE)
            confidence = conf_match.group(1).lower() if conf_match else "medium"
            
            return {
                "answer": answer,
                "citations": [],
                "confidence": confidence,
                "assumptions": []
            }
        
        return None
    
    async def answer(self, query: str, chunks: List[Chunk]) -> ChatResponse:
        """
        Generate an answer grounded in the provided chunks.
        """
        context_str = ""
        if not chunks:
            context_str = "No relevant code chunks found in the repository. The user might be asking a general question."
        else:
            # Build context string with truncation
            context_parts = []
            for i, chunk in enumerate(chunks):
                content = chunk.content
                if len(content) > self.MAX_CONTENT_LENGTH:
                    content = content[:self.MAX_CONTENT_LENGTH] + "... [truncated]"
                
                context_parts.append(
                    f"[Source {i+1}]\n"
                    f"File: {chunk.file_path}\n"
                    f"Lines: {chunk.line_range}\n"
                    f"Content:\n{content}\n"
                )
            context_str = "\n---\n".join(context_parts)
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {query}"}
        ]
        
        try:
            response_text = await llm.chat_completion(messages, json_mode=True)
            
            # Parse the response
            data = self._parse_response(response_text)
            
            if data:
                # Clean up the answer field
                data["answer"] = _clean_answer_text(data.get("answer", ""))
                
                # Ensure confidence is valid - preserve LLM's confidence
                confidence = data.get("confidence", "medium")
                if isinstance(confidence, str):
                    confidence = confidence.lower()
                    if confidence not in ["high", "medium", "low"]:
                        confidence = "medium"
                data["confidence"] = confidence
                
                # If LLM returned empty citations but we have chunks, inject them
                if (not data.get("citations") or len(data.get("citations", [])) == 0) and chunks:
                    data["citations"] = self._generate_citations_from_chunks(chunks)
                    logger.info("injected_fallback_citations", count=len(data["citations"]))
                
                return ChatResponse(**data)
            
            # Fallback: Could not parse response
            fallback_answer = _clean_answer_text(response_text)
            fallback_citations = self._generate_citations_from_chunks(chunks) if chunks else []
            
            return ChatResponse(
                answer=fallback_answer if fallback_answer else "I couldn't generate a proper response.",
                citations=fallback_citations,
                confidence=AnswerConfidence.MEDIUM,  # Not low - just couldn't parse
                assumptions=["Response format was not valid JSON"]
            )
                
        except Exception as e:
            logger.error("answer_generation_failed", error=str(e))
            error_citations = self._generate_citations_from_chunks(chunks) if chunks else []
            return ChatResponse(
                answer=f"Sorry, I encountered an error while generating the answer.\n\nError details: {str(e)}",
                citations=error_citations,
                confidence=AnswerConfidence.LOW,
                assumptions=[str(e)]
            )


# Global instance
answerer = Answerer()
