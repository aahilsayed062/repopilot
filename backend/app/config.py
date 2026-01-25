"""
Configuration settings for RepoPilot AI.
Loads from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv


# Explicitly load .env from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Get project root (parent of backend/)
# __file__ = backend/app/config.py -> .parent = app -> .parent = backend -> .parent = repopilot
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=env_path,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # App info

    app_name: str = "RepoPilot AI"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")

    openai_embedding_model: str = "text-embedding-ada-002"
    openai_chat_model: str = "gpt-4o"

    # Gemini
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")

    gemini_embedding_model: str = "models/text-embedding-004"
    gemini_chat_model: str = "gemini-2.0-flash"
    
    # Paths - use absolute path
    data_dir: Path = Field(default=PROJECT_ROOT / "data", validation_alias="DATA_DIR")

    
    # Repo constraints
    max_repo_size_mb: int = 100  # Reject repos larger than this
    max_files: int = 5000  # Maximum files to process
    
    # Chunking
    code_chunk_lines: int = 150
    code_chunk_overlap: int = 20
    doc_chunk_tokens: int = 1000
    doc_chunk_overlap: int = 100
    
    # Retrieval
    top_k: int = 8
    
    # Server
    host: str = "0.0.0.0"
    port: int = Field(default=8000, validation_alias="PORT")

    
    @field_validator("openai_api_key", "gemini_api_key", mode="before")
    @classmethod
    def _normalize_api_key(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None
    
    @property
    def use_mock_embeddings(self) -> bool:
        """Use mock embeddings if no API key is set."""
        return (not self.openai_api_key) and (not self.gemini_api_key)

    
    def get_repo_path(self, repo_name: str, commit_hash: str) -> Path:
        """Get the path for a specific repo version."""
        return self.data_dir / repo_name / commit_hash
    

# Global settings instance
settings = Settings()
