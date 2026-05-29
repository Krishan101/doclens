from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Postgres
    database_url: str = "postgresql+asyncpg://doclens:doclens_secret@postgres:5432/doclens"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    jwt_secret_key: str = "change-this-to-a-random-string-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Groq
    groq_api_key: str = ""
    llm_primary_model: str = "llama-3.3-70b-versatile"
    llm_fallback_model: str = "llama-3.1-8b-instant"

    # RAG
    max_context_tokens: int = 2000
    max_completion_tokens: int = 512
    relevance_threshold: float = 0.3

    # Upload
    max_upload_size_mb: int = 20
    backend_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
