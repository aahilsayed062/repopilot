"""
Retriever service - Semantic search over indexed chunks.
"""

import re
from typing import List

from app.config import settings
from app.utils.logger import get_logger
from app.models.chunk import Chunk, ChunkMetadata
from app.services.indexer import indexer
from app.utils.embeddings import embedding_service

logger = get_logger(__name__)


class Retriever:
    """
    Retrieves relevant chunks for a query using semantic search.
    """
    
    def __init__(self, default_k: int = 3):
        # Reduced to 3 for faster CPU inference (less context = faster LLM)
        self.default_k = default_k

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z0-9_]{2,}", (text or "").lower()))
    
    async def retrieve(self, repo_id: str, query: str, k: int = None) -> List[Chunk]:
        """
        Retrieve top-k relevant chunks.
        """
        k = k or self.default_k or settings.top_k
        logger.info("retrieving_chunks", repo_id=repo_id, query=query, k=k)
        
        # Get collection
        collection = indexer.get_collection(repo_id)
        if not collection:
            logger.warning("index_not_found", repo_id=repo_id)
            return []
        
        # Embed query
        # Note: We wrap in list because service expects batch
        query_embeddings = await embedding_service.embed_batch([query])
        
        if not query_embeddings:
            return []
            
        # Search
        search_k = max(k * 3, 12)
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=search_k,
            include=["documents", "metadatas", "distances"]
        )
        
        # Parse results
        chunks = []
        
        # Chroma returns lists of lists (one per query)
        if not results["ids"] or not results["ids"][0]:
            return []
            
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0] if "distances" in results else []
        query_tokens = self._tokenize(query)
        scored = []
        
        for i, chunk_id in enumerate(ids):
            meta = metadatas[i]
            content = documents[i]
            
            # Reconstruct Chunk object
            chunk = Chunk(
                metadata=ChunkMetadata(
                    chunk_id=chunk_id,
                    repo_id=meta["repo_id"],
                    file_path=meta["file_path"],
                    start_line=meta["start_line"],
                    end_line=meta["end_line"],
                    language=meta["language"],
                    chunk_type=meta["chunk_type"],
                    token_count=meta["token_count"]
                ),
                content=content
            )
            # Hybrid rerank: lexical overlap + vector distance
            lexical = 0.0
            if query_tokens:
                content_tokens = self._tokenize(content) | self._tokenize(meta["file_path"])
                overlap = len(query_tokens & content_tokens)
                lexical = overlap / max(1, len(query_tokens))

            semantic = 0.0
            if i < len(distances):
                try:
                    semantic = 1.0 / (1.0 + float(distances[i]))
                except Exception:
                    semantic = 0.0

            total_score = (0.7 * lexical) + (0.3 * semantic)
            scored.append((total_score, chunk))
            
        scored.sort(key=lambda item: item[0], reverse=True)
        chunks = [chunk for _, chunk in scored[:k]]
        logger.info("retrieved_chunks", count=len(chunks))
        return chunks


# Global instance
retriever = Retriever()
