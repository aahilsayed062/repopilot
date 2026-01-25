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
    
    SYSTEM_PROMPT = """You are RepoPilot, a grounded engineering assistant.
    Answer the user's question using ONLY the provided context snippets.
    
    Rules:
    1. If the answer is not in the context, say "I cannot find evidence for this in the provided context." do not guess.
    2. Cite your sources. For every statement, provide the file path and line range.
    3. Do not assume behavior not visible in the code.
    4. Provide your response in JSON format matching the schema.
    5. If asked for general knowledge unconnected to the repo, refuse politely.
    
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
        # Improvement: Guardrails for out-of-scope queries
        out_of_scope_keywords = ["joke", "weather", "poem", "story", "personal", "who are you"]
        if any(kw in query.lower() for kw in out_of_scope_keywords) and not chunks:
            return ChatResponse(
                answer="I am RepoPilot, an AI engineering assistant. I can only assist with codebase-related questions based on the provided repositories. I cannot fulfill general knowledge or creative writing requests.",
                citations=[],
                confidence="high",
                assumptions=["Query identified as out-of-scope."]
            )

        if not chunks:
            return ChatResponse(
                answer="I could not find any relevant code or documentation to answer your question.",
                citations=[],
                confidence=AnswerConfidence.LOW,
            )
        
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
                answer="Sorry, I encountered an error while generating the answer.",
                citations=[],
                confidence=AnswerConfidence.LOW,
                assumptions=[str(e)]
            )


# Global instance
answerer = Answerer()
