"""Тесты health-check эндпоинта."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health_check(client):
    """Health-check возвращает 200 и статус ok."""
    mock_conn = AsyncMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("src.routes.health.engine", mock_engine):
        ac, _ = client
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "API Hub"


@pytest.mark.asyncio
async def test_health_db_error(client):
    """Health-check при ошибке БД."""
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("DB down")

    with patch("src.routes.health.engine", mock_engine):
        ac, _ = client
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data["database"]


@pytest.mark.asyncio
async def test_health_returns_version(client):
    """Health-check содержит версию сервиса."""
    mock_conn = AsyncMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("src.routes.health.engine", mock_engine):
        ac, _ = client
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
