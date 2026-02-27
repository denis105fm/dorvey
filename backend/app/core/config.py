"""Application configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """App settings from env."""

    # App
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    API_PREFIX: str = "/api"
    # Публичный URL приложения (для OAuth redirect_uri за прокси). Пример: https://app.fortboyard31.ru
    PUBLIC_APP_URL: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dorvey:dorvey@localhost:5432/dorvey"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Telegram (optional)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Email (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@dorvey.local"

    # S3 / MinIO / Cloudflare R2
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "dorvey"
    S3_REGION: str = "us-east-1"

    # Default admin (created on first deploy if no users exist)
    DEFAULT_ADMIN_EMAIL: str = "admin@dorvey.local"
    DEFAULT_ADMIN_PASSWORD: str = "ChangeMeNow123!"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
