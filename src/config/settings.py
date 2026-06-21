"""Настройки приложения из переменных окружения."""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Приложение
    APP_NAME: str = "API Hub"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # База данных
    DATABASE_URL: str = "postgresql+asyncpg://apihub:apihub@localhost:5432/apihub"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Vault
    VAULT_ADDR: str = "http://localhost:8200"
    VAULT_TOKEN: str = ""

    # API Hub мастер-ключ (для авторизации агентов)
    MASTER_KEY: str = "change-me-in-production"

    # Лимиты
    DEFAULT_RATE_LIMIT_PER_MINUTE: int = 60
    DEFAULT_RATE_LIMIT_PER_DAY: int = 10000

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
