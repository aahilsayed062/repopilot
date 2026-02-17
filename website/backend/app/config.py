"""
Configuration settings for RepoPilot Website API.
Lightweight config — only needs GEMINI_API_KEY for LLM analysis.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv


def _resolve_project_root() -> Path:
    """Resolve repo root for local and container deployments."""
    current = Path(__file__).resolve()
    backend_root = current.parents[1]
    if backend_root.name == "backend":
        return backend_root.parent
    return backend_root


PROJECT_ROOT = _resolve_project_root()

# Explicitly load .env from backend dir
env_path = PROJECT_ROOT / "backend" / ".env"
if not env_path.exists():
    env_path = PROJECT_ROOT / ".env"
load_dotenv(env_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=env_path,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # App info
    app_name: str = "RepoPilot Website"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Gemini (primary LLM for architecture analysis)
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_chat_model: str = "gemini-2.0-flash"
    
    # Repo constraints
    max_repo_size_mb: int = Field(default=250, validation_alias="MAX_REPO_SIZE_MB")
    clone_timeout_seconds: int = Field(default=60, validation_alias="CLONE_TIMEOUT_SECONDS")
    
    # Rate limiting
    max_analyses_per_hour: int = Field(default=10, validation_alias="MAX_ANALYSES_PER_HOUR")
    
    # Server
    host: str = "0.0.0.0"
    port: int = Field(default=8001, validation_alias="PORT")
    
    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _normalize_api_key(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


# Global settings instance
settings = Settings()
