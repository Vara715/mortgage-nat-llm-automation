"""
config.py
=========
Global configuration and environment settings for mortgage_assistant.
Supports configurable LLM, embedding providers, database, and jurisdiction controls.
"""

from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "mortgage_assistant"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = Field(default="development", description="development, staging, or production")
    
    # Message Broker & Orchestration
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    N8N_WEBHOOK_URL: str = Field(default="http://localhost:5678", description="n8n service base URL")
    
    # Database configuration (Defaults to high-speed local SQLite with WAL mode, supports PostgreSQL)
    DATABASE_URL: str = Field(
        default=f"sqlite:///{BASE_DIR}/data/processed/mortgage_assistant.db",
        description="SQLAlchemy database connection string",
    )

    # Storage paths
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    REPORTS_DIR: Path = BASE_DIR / "data" / "reports"

    # AI & Retrieval configurations
    EMBEDDING_PROVIDER: str = Field(default="tfidf_dense", description="'tfidf_dense', 'sentence_transformers', or 'openai'")
    LLM_PROVIDER: str = Field(default="mock_or_env", description="'openai', 'groq', 'nim', or 'mock_or_env'")
    OPENAI_API_KEY: Optional[str] = None
    NVIDIA_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    DEFAULT_LLM_MODEL: str = "meta/llama-3-70b-instruct"

    # Retrieval parameters
    HYBRID_SEARCH_TOP_K: int = 5
    BM25_WEIGHT: float = 0.6
    DENSE_WEIGHT: float = 0.4
    MIN_SIMILARITY_SCORE: float = 0.15

    # Jurisdiction validation
    SUPPORTED_JURISDICTIONS: List[str] = ["US", "IN"]

    # Security & Upload constraints
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".txt", ".json", ".csv"]
    CORS_ORIGINS: List[str] = ["*"]

    # JWT & Authentication
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production-32chars",
        description="JWT secret key",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=480,
        description="JWT token expiry in minutes (8 hours)",
    )

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable API rate limiting")


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
