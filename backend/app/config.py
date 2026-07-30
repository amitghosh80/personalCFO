from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet
from functools import lru_cache


class Settings(BaseSettings):
    encryption_key: str = ""
    database_url: str = "sqlite:///./personalcfo.db"
    max_upload_size_mb: int = 20  # PRD F1: ~5 years of monthly statements
    anthropic_api_key: str = ""
    ai_categorizer_model: str = "claude-haiku-4-5"
    chat_model: str = "claude-sonnet-4-6"
    jwt_secret: str = ""
    jwt_expire_minutes: int = 60 * 24 * 30  # 30 days
    # Comma-separated list of extra allowed CORS origins (prod frontend domain).
    allowed_origins: str = ""
    sentry_dsn: str = ""
    environment: str = "development"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not set in environment")
    return Fernet(key.encode())
