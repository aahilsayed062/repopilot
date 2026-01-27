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
    
    # Limit per-chunk content to avoid token overflow with Groq's 12k TPM
    MAX_CONTENT_LENGTH = 600
    
    SYSTEM_PROMPT = """You are RepoPilot, a helpful engineering assistant.
    You have access to a codebase, but you can also answer general software engineering questions.
    
    Rules:
    1. If the user asks about the codebase and you have context:
       - Answer using ONLY the provided context snippets.
       - Cite your sources (file path and line range).
    2. If the user asks about the codebase but you have NO context:
       - Do NOT guess about the code.
       - Provide suggestions on what file names or search terms might be relevant.
       - Offer general knowledge if applicable (e.g. "I couldn't find 'AuthService', but typically authentication handles...").
       - Explicitly state you are answering from general knowledge.
    3. If the user asks a general coding question (unrelated to the repo):
       - Answer helpfuly using your general knowledge.
    4. Provide your response in JSON format matching the schema.
    
    Response Schema:
    {
        "answer": "markdown text",
        "citations": [
            {
                "file_path": "path/to/file",
                "line_range": "L10-L20",
                "snippet": "exact code quote",
                "why": "explanation"
            }
        ],
        "confidence": "high|medium|low",
        "assumptions": ["list of assumptions if any"]
    }
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
