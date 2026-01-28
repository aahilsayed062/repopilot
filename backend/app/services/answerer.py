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
    
    SYSTEM_PROMPT = """You are RepoPilot, a helpful coding assistant that answers questions about codebases.

Rules:
1. If you have context from the codebase, use it to answer accurately.
2. If no relevant context is found, provide helpful general information.
3. Be concise and actionable.

IMPORTANT: Return your response as a JSON object with this exact structure:
{
    "answer": "Your answer here as plain markdown text. Do NOT include JSON in this field.",
    "citations": [
        {"file_path": "path/to/file", "line_range": "L10-L20", "snippet": "code", "why": "reason"}
    ],
    "confidence": "high" or "medium" or "low",
    "assumptions": ["any assumptions made"]
}

The "answer" field must contain ONLY readable markdown text, NOT JSON or code blocks containing JSON.
"""
    
    async def answer(self, query: str, chunks: List[Chunk]) -> ChatResponse:
        """
        Generate an answer grounded in the provided chunks.
        """
        # Improvement: Relaxed guards to allow general assistance
        
        context_str = ""
        if not chunks:
            context_str = "No relevant code chunks found in the repository. The user might be asking a general question or providing a query that didn't match existing files."
        else:
            # Build context string
            context_parts = []
            for i, chunk in enumerate(chunks):
                context_parts.append(
                    f"[Source {i+1}]\n"
                    f"File: {chunk.file_path}\n"
                    f"Lines: {chunk.line_range}\n"
                    f"Content:\n{chunk.content}\n"
                )
            context_str = "\n---\n".join(context_parts)
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {query}"}
        ]
        
        try:
            response_text = await llm.chat_completion(messages, json_mode=True)
            
            # Parse JSON
            # Note: Mock LLM returns markdown, not JSON, so handle that
            try:
                data = json.loads(response_text)
                return ChatResponse(**data)
            except json.JSONDecodeError:
                # Fallback for mock or malformed response
                return ChatResponse(
                    answer=response_text,
                    citations=[],
                    confidence=AnswerConfidence.LOW,
                    assumptions=["Response format was not valid JSON"]
                )
                
        except Exception as e:
            logger.error("answer_generation_failed", error=str(e))
            return ChatResponse(
                answer=f"Sorry, I encountered an error while generating the answer. \n\nError details: {str(e)}",
                citations=[],
                confidence=AnswerConfidence.LOW,
                assumptions=[str(e)]
            )


# Global instance
answerer = Answerer()
