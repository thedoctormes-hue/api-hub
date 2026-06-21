"""Подключение к базе данных."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import insert

from src.config.settings import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Дефолтные провайдеры для сидирования
DEFAULT_PROVIDERS = [
    {
        "name": "openrouter",
        "type": "llm",
        "base_url": "https://openrouter.ai/api/v1",
        "auth_type": "bearer",
        "auth_key_name": "Authorization",
        "rate_limit": 20,
        "timeout_sec": 30,
        "retry_count": 3,
        "retry_delay_ms": 1000,
        "is_active": True,
        "config": None,
    },
    {
        "name": "openai",
        "type": "llm",
        "base_url": "https://api.openai.com/v1",
        "auth_type": "bearer",
        "auth_key_name": "Authorization",
        "rate_limit": 60,
        "timeout_sec": 30,
        "retry_count": 3,
        "retry_delay_ms": 1000,
        "is_active": True,
        "config": None,
    },
    {
        "name": "anthropic",
        "type": "llm",
        "base_url": "https://api.anthropic.com",
        "auth_type": "header",
        "auth_key_name": "x-api-key",
        "rate_limit": 50,
        "timeout_sec": 60,
        "retry_count": 3,
        "retry_delay_ms": 1000,
        "is_active": True,
        "config": None,
    },
    {
        "name": "dadata",
        "type": "geocode",
        "base_url": "https://suggestions.dadata.ru/suggestions/api/4_1/rs",
        "auth_type": "header",
        "auth_key_name": "Authorization",
        "rate_limit": 30,
        "timeout_sec": 10,
        "retry_count": 2,
        "retry_delay_ms": 500,
        "is_active": True,
        "config": None,
    },
    {
        "name": "abstractapi",
        "type": "validate",
        "base_url": "https://emailvalidation.abstractapi.com/v1",
        "auth_type": "query_param",
        "auth_key_name": "api_key",
        "rate_limit": 10,
        "timeout_sec": 10,
        "retry_count": 2,
        "retry_delay_ms": 500,
        "is_active": True,
        "config": None,
    },
    {
        "name": "scraperapi",
        "type": "scrape",
        "base_url": "https://api.scraperapi.com",
        "auth_type": "query_param",
        "auth_key_name": "api_key",
        "rate_limit": 10,
        "timeout_sec": 30,
        "retry_count": 2,
        "retry_delay_ms": 1000,
        "is_active": True,
        "config": None,
    },
    {
        "name": "pdfgeneratorapi",
        "type": "generate",
        "base_url": "https://us1.pdfgeneratorapi.com/api/v4",
        "auth_type": "bearer",
        "auth_key_name": "Authorization",
        "rate_limit": 5,
        "timeout_sec": 30,
        "retry_count": 2,
        "retry_delay_ms": 1000,
        "is_active": True,
        "config": None,
    },
]


async def init_db():
    """Создать таблицы и сидировать провайдеров."""
    from src.models.provider import Provider

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Сидируем провайдеров (если их ещё нет)
    async with async_session() as session:
        for provider_data in DEFAULT_PROVIDERS:
            existing = await session.execute(
                select(Provider).where(Provider.name == provider_data["name"])
            )
            if not existing.scalar_one_or_none():
                session.add(Provider(**provider_data))
        await session.commit()


async def close_db():
    """Закрыть подключение при остановке."""
    await engine.dispose()


async def get_session() -> AsyncSession:
    """Получить сессию БД для dependency injection."""
    async with async_session() as session:
        yield session
