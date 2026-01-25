"""
Health check endpoint.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    version: str
    mock_mode: bool


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        HealthResponse with status, version, and mock mode indicator.
    """
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        mock_mode=settings.use_mock_embeddings
    )
