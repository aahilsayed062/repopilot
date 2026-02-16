"""
Application configuration loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration for the TaskFlow API."""

    APP_NAME: str = "TaskFlow API"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./taskflow.db")

    # JWT Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Rate limiting
    MAX_REQUESTS_PER_MINUTE: int = 60


settings = Settings()
