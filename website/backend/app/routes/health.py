"""
Health check endpoint for RepoPilot Website API.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    version: str
    gemini_configured: bool


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    Returns status, version, and whether Gemini API is configured.
    """
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        gemini_configured=bool(settings.gemini_api_key),
    )
