"""
Repository API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.repo import (
    RepoLoadRequest,
    RepoLoadResponse,
    RepoStatusResponse,
    RepoIndexRequest,
    RepoIndexResponse,
)
from app.services.repo_manager import (
    repo_manager,
    RepoManagerError,
    RepoCloneError,
    RepoTooLargeError,
)
from app.services.indexer import indexer
from app.utils.logger import get_logger

router = APIRouter(prefix="/repo", tags=["repository"])
logger = get_logger(__name__)


@router.post("/load", response_model=RepoLoadResponse)
async def load_repository(request: RepoLoadRequest) -> RepoLoadResponse:
    """
    Load a repository from GitHub URL or local path.
    
    Clones the repository (shallow clone) and stores it locally.
    Returns repository ID for subsequent operations.
    """
    try:
        repo_info = await repo_manager.load_repo(
            repo_url=request.repo_url,
            branch=request.branch
        )
        
        return RepoLoadResponse(
            success=True,
            repo_id=repo_info.repo_id,
            repo_name=repo_info.repo_name,
            commit_hash=repo_info.commit_hash,
            stats=repo_info.stats,
            message=f"Loaded {repo_info.repo_name} @ {repo_info.commit_hash[:8]}"
        )
        
    except RepoTooLargeError as e:
        logger.warning("repo_too_large", error=str(e))
        raise HTTPException(status_code=413, detail=str(e))
        
    except RepoCloneError as e:
        logger.error("repo_clone_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.exception("repo_load_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to load repository: {e}")


@router.get("/status", response_model=RepoStatusResponse)
async def get_repository_status(
    repo_id: str = Query(..., description="Repository ID"),
    include_files: bool = Query(default=False, description="Include file list")
) -> RepoStatusResponse:
    """
    Get status and statistics for a loaded repository.
    
    Optionally includes list of all indexed files.
    """
    repo_info = repo_manager.get_repo(repo_id)
    
    if not repo_info:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")
    
    files = None
    if include_files:
        try:
            files = await repo_manager.list_files(repo_id)
        except RepoManagerError as e:
            logger.error("file_list_error", error=str(e))
    
    return RepoStatusResponse(
        repo_id=repo_info.repo_id,
        repo_name=repo_info.repo_name,
        exists=True,
        indexed=repo_info.indexed,
        stats=repo_info.stats,
        chunk_count=repo_info.chunk_count,
        is_indexing=repo_info.is_indexing,
        index_progress_pct=repo_info.index_progress_pct,
        index_processed_chunks=repo_info.index_processed_chunks,
        index_total_chunks=repo_info.index_total_chunks,
        files=files
    )


@router.post("/index", response_model=RepoIndexResponse)
async def index_repository(request: RepoIndexRequest) -> RepoIndexResponse:
    """
    Index a repository for semantic search.
    
    Creates embeddings for all chunks and stores in vector database.
    """
    repo_info = repo_manager.get_repo(request.repo_id)
    
    if not repo_info:
        raise HTTPException(status_code=404, detail=f"Repository not found: {request.repo_id}")
    
    if repo_info.indexed and not request.force:
        return RepoIndexResponse(
            success=True,
            repo_id=request.repo_id,
            indexed=True,
            chunk_count=repo_info.chunk_count,
            message="Repository already indexed. Use force=true to re-index."
        )
    
    try:
        result = await indexer.index_repo(request.repo_id)
        
        return RepoIndexResponse(
            success=True,
            repo_id=request.repo_id,
            indexed=True,
            chunk_count=result["chunk_count"],
            message=f"Successfully indexed {result['chunk_count']} chunks."
        )
    except Exception as e:
        logger.exception("indexing_failed", repo_id=request.repo_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")
