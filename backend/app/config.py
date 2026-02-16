"""
Configuration settings for RepoPilot AI.
Loads from environment variables with sensible defaults.
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

# Explicitly load .env from project root
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
    app_name: str = "RepoPilot AI"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, validation_alias="OPENAI_BASE_URL")

    openai_embedding_model: str = "text-embedding-ada-002"
    openai_chat_model: str = "gpt-4o"

    # Gemini
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")

    gemini_embedding_model: str = "models/gemini-embedding-001"
    gemini_chat_model: str = "gemini-2.0-flash"

    # Ollama (local offline LLM)
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model_a: str = Field(default="qwen2.5-coder:1.5b", validation_alias="OLLAMA_MODEL_A")
    ollama_model_b: str = Field(default="qwen2.5-coder:3b", validation_alias="OLLAMA_MODEL_B")
    ollama_embed_model: str = Field(default="nomic-embed-text", validation_alias="OLLAMA_EMBED_MODEL")
    
    # Paths - use absolute path
    data_dir: Path = Field(default=PROJECT_ROOT / "data", validation_alias="DATA_DIR")

    
    # Repo constraints
    max_repo_size_mb: int = Field(default=512, validation_alias="MAX_REPO_SIZE_MB")
    max_files: int = Field(default=10000, validation_alias="MAX_FILES")
    clone_timeout_seconds: int = Field(default=900, validation_alias="CLONE_TIMEOUT_SECONDS")
    
    # Chunking
    code_chunk_lines: int = 150
    code_chunk_overlap: int = 20
    doc_chunk_tokens: int = 500
    doc_chunk_overlap: int = 100

    # Indexing performance
    index_batch_size: int = Field(default=250, validation_alias="INDEX_BATCH_SIZE")
    file_read_concurrency: int = Field(default=32, validation_alias="FILE_READ_CONCURRENCY")
    index_max_files: int = Field(default=900, validation_alias="INDEX_MAX_FILES")
    index_max_file_size_kb: int = Field(default=256, validation_alias="INDEX_MAX_FILE_SIZE_KB")
    index_max_total_mb: int = Field(default=20, validation_alias="INDEX_MAX_TOTAL_MB")
    index_max_chunks: int = Field(default=2500, validation_alias="INDEX_MAX_CHUNKS")
    index_time_budget_seconds: int = Field(default=55, validation_alias="INDEX_TIME_BUDGET_SECONDS")
    use_persistent_index: bool = Field(default=False, validation_alias="USE_PERSISTENT_INDEX")
    
    # Retrieval
    top_k: int = 3
    
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
