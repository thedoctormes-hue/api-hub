"""Тестовые фикстуры с SQLite in-memory и dependency override."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import patch, AsyncMock

from src.main import app
from src.config.database import Base, get_session


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    """Тестовый клиент с in-memory SQLite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session = session_maker()

    # Override get_session dependency — тот же async generator, но с тестовой сессией
    async def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session

    # Мокаем init_db/close_db чтобы не трогать PostgreSQL
    with patch("src.main.init_db", new_callable=AsyncMock), \
         patch("src.main.close_db", new_callable=AsyncMock):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, test_session

    app.dependency_overrides.clear()
    await test_session.close()
    await engine.dispose()
