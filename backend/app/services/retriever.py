"""
Retriever service - Semantic search over indexed chunks.
"""

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
    
    def __init__(self, default_k: int = 8):
        self.default_k = default_k
    
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
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=k,
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
        # distances = results["distances"][0] if "distances" in results else []
        
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
            chunks.append(chunk)
            
        logger.info("retrieved_chunks", count=len(chunks))
        return chunks


# Global instance
retriever = Retriever()
