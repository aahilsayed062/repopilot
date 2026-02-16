"""
Embedding Service - Handles text embeddings for vector search.

Priority: Ollama (local, fast, no limits) > Gemini (free API) > OpenAI (paid) > Mock

Why Ollama first?
1. ZERO rate limits - runs locally
2. Fast - no network latency
3. Free - no API costs
4. all-minilm produces 384-dim vectors (fast, lightweight)
   Fallback: Gemini embedding-001 produces 768-dim vectors
"""

import asyncio
import hashlib
import re
import numpy as np
import zlib
from typing import List
import backoff
import httpx
from openai import AsyncOpenAI, OpenAIError
from google import genai
from google.genai import types

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Gemini free-tier: 100 embedding requests/minute.
GEMINI_SUB_BATCH_SIZE = 20
GEMINI_SUB_BATCH_DELAY = 1.5
GEMINI_429_BASE_WAIT = 62.0
GEMINI_429_MAX_RETRIES = 3

# Ollama - small batches to avoid timeouts on consumer hardware
OLLAMA_BATCH_SIZE = 50  # texts per API call (all-minilm is fast enough for 50)


class EmbeddingService:
    """Generates embeddings for text chunks.

    Priority: Ollama > Gemini > OpenAI > Mock
    """

    # Embedding dimensions by provider
    OLLAMA_DIM = 384    # all-minilm default (faster, smaller)
    OLLAMA_DIM_NOMIC = 768  # nomic-embed-text
    GEMINI_DIM = 768
    OPENAI_DIM = 1536

    def __init__(self):
        self.openai_client = None
        self.gemini_client = None
        self.provider = "mock"
        self.dimension = self.GEMINI_DIM
        self.ollama_base_url = settings.ollama_base_url
        self.ollama_embed_model = settings.ollama_embed_model

        # Priority 1: Ollama (local, fast, no rate limits)
        if self._check_ollama_embed_available():
            self.provider = "ollama"
            # Auto-detect dimension based on model name
            model_lower = self.ollama_embed_model.lower()
            if "minilm" in model_lower:
                self.dimension = 384
            elif "nomic" in model_lower:
                self.dimension = self.OLLAMA_DIM_NOMIC
            else:
                self.dimension = self.OLLAMA_DIM
            
            logger.info(
                "embeddings_initialized",
                provider="Ollama",
                model=self.ollama_embed_model,
                note=f"Local embeddings ({self.dimension}d) - no rate limits!",
            )
        # Priority 2: Gemini (free API, but rate-limited)
        elif settings.gemini_api_key:
            self.gemini_client = genai.Client(api_key=settings.gemini_api_key)
            self.provider = "gemini"
            self.dimension = self.GEMINI_DIM
            logger.info(
                "embeddings_initialized",
                provider="Gemini",
                model=settings.gemini_embedding_model,
            )
        # Priority 3: OpenAI (paid)
        elif settings.openai_api_key:
            if settings.openai_base_url and "groq" in settings.openai_base_url.lower():
                self.provider = "mock"
                logger.warning(
                    "embeddings_initialized",
                    provider="mock",
                    reason="Groq does not support embeddings",
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
                reason="No API key or Ollama configured",
            )

    def _check_ollama_embed_available(self) -> bool:
        """Check if Ollama is running and has the embedding model pulled."""
        try:
            resp = httpx.get(f"{self.ollama_base_url}/api/tags", timeout=3.0)
            if resp.status_code != 200:
                return False
            available = {m["name"] for m in resp.json().get("models", [])}
            model = self.ollama_embed_model
            base = model.split(":")[0]
            return any(a == model or a.startswith(base + ":") for a in available)
        except Exception:
            return False

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a list of texts."""
        if not texts:
            return []

        try:
            if self.provider == "ollama":
                return await self._get_ollama_embeddings(texts)
            elif self.provider == "gemini":
                return await self._get_gemini_embeddings(texts)
            elif self.provider == "openai":
                return await self._get_openai_embeddings(texts)
            else:
                return await asyncio.to_thread(self._get_mock_embeddings, texts)
        except Exception as e:
            error_detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            logger.error("embedding_failed", provider=self.provider, error=error_detail)
            # Fallback chain: try Gemini if Ollama fails, then mock
            if self.provider == "ollama" and settings.gemini_api_key:
                logger.warning("falling_back_to_gemini_embeddings")
                try:
                    if not self.gemini_client:
                        self.gemini_client = genai.Client(api_key=settings.gemini_api_key)
                    return await self._get_gemini_embeddings(texts)
                except Exception as e2:
                    logger.error("gemini_fallback_failed", error=str(e2))
            logger.warning("falling_back_to_mock_embeddings")
            return await asyncio.to_thread(self._get_mock_embeddings, texts)

    def _get_mock_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate deterministic fake embeddings."""
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

    async def _get_ollama_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from local Ollama. No rate limits, fast.
        
        Uses small batches and per-text fallback to handle slow hardware gracefully.
        """
        all_embeddings: List[List[float]] = []
        total_batches = (len(texts) + OLLAMA_BATCH_SIZE - 1) // OLLAMA_BATCH_SIZE

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            for i in range(0, len(texts), OLLAMA_BATCH_SIZE):
                sub_batch = texts[i:i + OLLAMA_BATCH_SIZE]
                batch_num = (i // OLLAMA_BATCH_SIZE) + 1

                try:
                    response = await client.post(
                        f"{self.ollama_base_url}/api/embed",
                        json={
                            "model": self.ollama_embed_model,
                            "input": sub_batch,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    all_embeddings.extend(data["embeddings"])

                    logger.debug(
                        "ollama_embed_batch_ok",
                        batch=f"{batch_num}/{total_batches}",
                        texts=len(sub_batch),
                    )
                except Exception as batch_err:
                    # Batch failed — fall back to embedding one text at a time
                    logger.warning(
                        "ollama_batch_failed_trying_individual",
                        batch=f"{batch_num}/{total_batches}",
                        error=f"{type(batch_err).__name__}: {batch_err}",
                    )
                    for j, text in enumerate(sub_batch):
                        try:
                            resp = await client.post(
                                f"{self.ollama_base_url}/api/embed",
                                json={
                                    "model": self.ollama_embed_model,
                                    "input": [text],
                                },
                            )
                            resp.raise_for_status()
                            data = resp.json()
                            all_embeddings.extend(data["embeddings"])
                        except Exception as single_err:
                            logger.error(
                                "ollama_single_embed_failed",
                                text_index=i + j,
                                error=f"{type(single_err).__name__}: {single_err}",
                            )
                            raise

        return all_embeddings

    @staticmethod
    def _parse_retry_delay(error_msg: str) -> float:
        """Extract retryDelay from Gemini 429 error message."""
        match = re.search(r'retry in (\d+(?:\.\d+)?)s', str(error_msg))
        if match:
            return float(match.group(1)) + 2.0
        match = re.search(r"retryDelay.*?'(\d+)s'", str(error_msg))
        if match:
            return float(match.group(1)) + 2.0
        return GEMINI_429_BASE_WAIT

    async def _get_gemini_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from Gemini API with rate-limit-aware sub-batching."""
        model = settings.gemini_embedding_model
        if model.startswith("models/"):
            model = model[len("models/"):]

        clean_texts = [t.replace("\n", " ").strip() for t in texts]
        all_embeddings: List[List[float]] = []

        for i in range(0, len(clean_texts), GEMINI_SUB_BATCH_SIZE):
            sub_batch = clean_texts[i:i + GEMINI_SUB_BATCH_SIZE]
            batch_num = (i // GEMINI_SUB_BATCH_SIZE) + 1
            total_batches = (len(clean_texts) + GEMINI_SUB_BATCH_SIZE - 1) // GEMINI_SUB_BATCH_SIZE

            for attempt in range(GEMINI_429_MAX_RETRIES + 1):
                try:
                    result = await self.gemini_client.aio.models.embed_content(
                        model=model,
                        contents=sub_batch,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                        ),
                    )
                    all_embeddings.extend(emb.values for emb in result.embeddings)
                    logger.debug(
                        "gemini_sub_batch_ok",
                        batch=f"{batch_num}/{total_batches}",
                        texts=len(sub_batch),
                    )
                    break
                except Exception as e:
                    error_str = str(e)
                    is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
                    if is_rate_limit and attempt < GEMINI_429_MAX_RETRIES:
                        wait_time = self._parse_retry_delay(error_str)
                        logger.warning(
                            "gemini_rate_limited",
                            batch=f"{batch_num}/{total_batches}",
                            attempt=attempt + 1,
                            wait_seconds=round(wait_time, 1),
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error("gemini_embedding_failed", batch=f"{batch_num}/{total_batches}", error=error_str)
                        raise

            if i + GEMINI_SUB_BATCH_SIZE < len(clean_texts):
                await asyncio.sleep(GEMINI_SUB_BATCH_DELAY)

        return all_embeddings

    @backoff.on_exception(backoff.expo, OpenAIError, max_tries=3)
    async def _get_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI API."""
        try:
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
