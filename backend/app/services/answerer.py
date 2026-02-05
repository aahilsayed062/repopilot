"""
Answerer Service - Generates grounded answers from retrieved chunks.
"""

import json
from typing import List

from app.utils.logger import get_logger
from app.utils.llm import llm
from app.models.chunk import Chunk
from app.models.chat import ChatResponse, Citation, AnswerConfidence

logger = get_logger(__name__)


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
    
    async def answer(self, query: str, chunks: List[Chunk]) -> ChatResponse:
        """
        Generate an answer grounded in the provided chunks.
        """
        # Improvement: Relaxed guards to allow general assistance
        
        context_str = ""
        if not chunks:
            context_str = "No relevant code chunks found in the repository. The user might be asking a general question or providing a query that didn't match existing files."
        else:
            # Build context string with truncation
            context_parts = []
            for i, chunk in enumerate(chunks):
                # Truncate content to avoid token overflow
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
            
            # Parse JSON
            # Clean up markdown code blocks if present (Groq/Llama-3 sometimes includes them even in JSON mode)
            # Clean up markdown code blocks if present
            clean_text = response_text.strip()
            if clean_text.startswith("```"):
                import re
                clean_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean_text, flags=re.MULTILINE)
            
            clean_text = clean_text.strip()
            
            # Helper to attempt parsing
            def parse_json(text):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return None

            # Strategy 1: Direct Parse
            data = parse_json(clean_text)
            
            # Strategy 2: Fix missing braces (Llama-3 sometimes returns just "key": "value")
            if not data and not clean_text.startswith("{"):
                data = parse_json(f"{{{clean_text}}}")
                
            # Strategy 3: Regex extraction of the 'answer' field
            if not data:
                import re
                # Match "answer": "..." (handling simple escaped quotes)
                match = re.search(r'"answer"\s*:\s*"(.*?)(?<!\\)"', clean_text, re.DOTALL)
                if match:
                    data = {
                        "answer": match.group(1).encode('utf-8').decode('unicode_escape'),
                        "citations": [],
                        "confidence": "low",
                        "assumptions": ["Extracted answer via regex"]
                    }
            
            if data:
                # CRITICAL FIX: If LLM returned empty citations but we have chunks, inject them
                if (not data.get("citations") or len(data.get("citations", [])) == 0) and chunks:
                    data["citations"] = self._generate_citations_from_chunks(chunks)
                    logger.info("injected_fallback_citations", count=len(data["citations"]))
                return ChatResponse(**data)
            
            # Fallback: Treat whole text as answer if it doesn't look like JSON
            # Still inject citations from chunks if available
            fallback_citations = self._generate_citations_from_chunks(chunks) if chunks else []
            return ChatResponse(
                answer=response_text,
                citations=fallback_citations,
                confidence=AnswerConfidence.LOW,
                assumptions=["Response format was not valid JSON"]
            )
                
        except Exception as e:
            logger.error("answer_generation_failed", error=str(e))
            # Still provide citations from chunks even on error
            error_citations = self._generate_citations_from_chunks(chunks) if chunks else []
            return ChatResponse(
                answer=f"Sorry, I encountered an error while generating the answer. \n\nError details: {str(e)}",
                citations=error_citations,
                confidence=AnswerConfidence.LOW,
                assumptions=[str(e)]
            )


# Global instance
answerer = Answerer()
