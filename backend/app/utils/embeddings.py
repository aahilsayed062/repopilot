"""
Embedding service handling OpenAI, Gemini, and Mock embeddings.
"""

import hashlib
import numpy as np
from typing import List
import backoff
from openai import AsyncOpenAI, OpenAIError
import google.generativeai as genai

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Generates embeddings for text chunks."""
    
    def __init__(self):
        self.openai_client = None
        self.using_gemini = False
        
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.using_gemini = True
        elif settings.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a list of texts."""
        if not texts:
            return []
            
        if self.using_gemini:
             return await self._get_gemini_embeddings(texts)
        elif self.openai_client:
            return await self._get_openai_embeddings(texts)
        else:
            return self._get_mock_embeddings(texts)
    
    def _get_mock_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate deterministic fake embeddings."""
        embeddings = []
        for text in texts:
            # Deterministic hash to seed random
            hash_bytes = hashlib.sha256(text.encode()).digest()
            seed = int.from_bytes(hash_bytes[:4], 'big')
            rng = np.random.RandomState(seed)
            # 1536 dimensions like ada-002 (Gemini uses 768)
            # Use 768 if Gemini might be used later? 
            # Chroma works with whatever dim you start with, but mixing is bad.
            # Mock = 768 for compatibility with Gemini standard
            dim = 768 if self.using_gemini else 1536 
            vector = rng.randn(dim).tolist()
            # Normalize
            norm = np.linalg.norm(vector)
            embeddings.append((vector / norm).tolist())
        return embeddings

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def _get_gemini_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Call Gemini API."""
        try:
            # Gemini batch embedding
            # "models/text-embedding-004"
            model = settings.gemini_embedding_model
            
            # API expects: content or list of contents
            # Google's Python SDK for batch processing:
            # result = genai.embed_content(model=model, content=texts, task_type="retrieval_document")
            # Note: embed_content can take a list.
            
            # Clean newlines just in case
            clean_texts = [t.replace("\n", " ") for t in texts]
            
            # Max batch size for Gemini? Usually 100 is fine.
            result = genai.embed_content(
                model=model,
                content=clean_texts,
                task_type="retrieval_document"
            )
            
            # Result is dictionary with 'embedding' if single, or list if multiple?
            # actually it's keys ['embedding']
            # If input is list, output 'embedding' is list of lists
            
            return result['embedding']
            
        except Exception as e:
            logger.error("gemini_embedding_failed", error=str(e))
            raise

    @backoff.on_exception(backoff.expo, OpenAIError, max_tries=3)
    async def _get_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Call OpenAI API with retry logic."""
        try:
            # Replace newlines as recommended by OpenAI
            clean_texts = [t.replace("\n", " ") for t in texts]
            
            response = await self.openai_client.embeddings.create(
                input=clean_texts,
                model=settings.openai_embedding_model
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error("openai_embedding_failed", error=str(e))
            raise

# Global instance
embedding_service = EmbeddingService()
