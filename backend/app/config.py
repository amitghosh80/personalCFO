from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet
from functools import lru_cache


class Settings(BaseSettings):
    encryption_key: str = ""
    database_url: str = "sqlite:///./personalcfo.db"
    max_upload_size_mb: int = 10

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
