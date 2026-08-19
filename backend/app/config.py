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
    chat_daily_limit: int = 50  # max /api/chat requests per user per day
    jwt_secret: str = ""
    jwt_expire_minutes: int = 60 * 24 * 30  # 30 days
    # OAuth client ID from Google Cloud Console — verifies the audience of
    # Google Sign-In ID tokens. Empty disables the /api/auth/google endpoint.
    google_client_id: str = ""
    # Comma-separated list of extra allowed CORS origins (prod frontend domain).
    allowed_origins: str = ""
    sentry_dsn: str = ""
    environment: str = "development"
    # Forgot-password email delivery via Resend (https://resend.com).
    resend_api_key: str = ""
    email_from: str = "PersonalCFO <onboarding@resend.dev>"
    # Base URL used to build password-reset links (prod: https://personalcfo.agency).
    frontend_url: str = "http://localhost:3000"

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
