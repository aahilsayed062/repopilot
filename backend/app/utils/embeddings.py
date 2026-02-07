"""
Embedding Service - Handles text embeddings for vector search.

Priority: Gemini > OpenAI > Mock (fallback)

This prioritizes Gemini for embeddings since:
1. Gemini embeddings are FREE (high quota)
2. OpenAI embeddings cost money
3. Groq doesn't support embeddings at all
"""

import asyncio
import hashlib
import numpy as np
import zlib
from typing import List
import backoff
from openai import AsyncOpenAI, OpenAIError
import google.generativeai as genai

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Generates embeddings for text chunks.

    Priority: Gemini > OpenAI > Mock
    """

    # Embedding dimensions by provider
    GEMINI_DIM = 768
    OPENAI_DIM = 1536

    def __init__(self):
        self.openai_client = None
        self.provider = "mock"  # 'gemini', 'openai', or 'mock'
        self.dimension = self.GEMINI_DIM  # Default to Gemini dimension

        # Priority: Gemini first (free & good), then OpenAI (paid), then mock
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.provider = "gemini"
            self.dimension = self.GEMINI_DIM
            logger.info(
                "embeddings_initialized",
                provider="Gemini",
                model=settings.gemini_embedding_model,
            )
        elif settings.openai_api_key:
            # Check if this is Groq (which doesn't support embeddings)
            if settings.openai_base_url and "groq" in settings.openai_base_url.lower():
                self.provider = "mock"
                logger.warning(
                    "embeddings_initialized",
                    provider="mock",
                    reason="Groq does not support embeddings, using mock",
                )
            elif settings.openai_embedding_model.lower().startswith("mock"):
                self.provider = "mock"
                logger.warning(
                    "embeddings_initialized",
                    provider="mock",
                    reason="Mock embedding model configured",
                )
            else:
                self.openai_client = AsyncOpenAI(
                    api_key=settings.openai_api_key, base_url=settings.openai_base_url
                )
                self.provider = "openai"
                self.dimension = self.OPENAI_DIM
                logger.info(
                    "embeddings_initialized",
                    provider="OpenAI",
                    model=settings.openai_embedding_model,
                )
        else:
            logger.warning(
                "embeddings_initialized",
                provider="mock",
                reason="No API key configured",
            )

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a list of texts."""
        if not texts:
            return []

        try:
            if self.provider == "gemini":
                return await self._get_gemini_embeddings(texts)
            elif self.provider == "openai":
                return await self._get_openai_embeddings(texts)
            else:
                return await asyncio.to_thread(self._get_mock_embeddings, texts)
        except Exception as e:
            logger.error("embedding_failed", provider=self.provider, error=str(e))
            # Fallback to mock if API fails
            logger.warning("falling_back_to_mock_embeddings")
            return await asyncio.to_thread(self._get_mock_embeddings, texts)

    def _get_mock_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate deterministic fake embeddings.

        Uses a fast hashing-trick bag-of-tokens vector.
        Deterministic across runs and significantly faster than per-text RNG.
        """
        embeddings = []
        dim = self.dimension
        token_cap = 256

        for text in texts:
            vector = np.zeros(dim, dtype=np.float32)
            tokens = text.split()

            if not tokens:
                tokens = [hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()]

            for token in tokens[:token_cap]:
                token_bytes = token.encode("utf-8", errors="ignore")
                h = zlib.crc32(token_bytes)
                idx = h % dim
                sign = 1.0 if (h & 1) else -1.0
                vector[idx] += sign

            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm

            embeddings.append(vector.tolist())
        return embeddings

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def _get_gemini_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from Gemini API."""
        try:
            model = settings.gemini_embedding_model

            # Clean text (Gemini can have issues with certain characters)
            clean_texts = [t.replace("\n", " ").strip() for t in texts]

            # genai.embed_content is synchronous -- run in thread to avoid blocking
            result = await asyncio.to_thread(
                genai.embed_content,
                model=model,
                content=clean_texts,
                task_type="retrieval_document",
            )

            # Result is {'embedding': [...]} for single or list of lists for batch
            return result["embedding"]

        except Exception as e:
            logger.error("gemini_embedding_failed", error=str(e))
            raise

    @backoff.on_exception(backoff.expo, OpenAIError, max_tries=3)
    async def _get_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI API."""
        try:
            # Replace newlines as recommended by OpenAI
            clean_texts = [t.replace("\n", " ").strip() for t in texts]

            response = await self.openai_client.embeddings.create(
                input=clean_texts, model=settings.openai_embedding_model
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error("openai_embedding_failed", error=str(e))
            raise


# Global instance
embedding_service = EmbeddingService()
