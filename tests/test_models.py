"""Тесты для /v1/models роута."""

import pytest
from src.models.provider import Provider


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_list_models_empty(client):
    """Список моделей при пустой базе."""
    ac, _ = client
    response = await ac.get("/v1/models")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_models_with_providers(client):
    """Список моделей с активными провайдерами."""
    ac, session = client

    provider = Provider(
        name="openrouter",
        type="llm",
        base_url="https://openrouter.ai/api/v1",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=20,
        timeout_sec=30,
        retry_count=3,
        retry_delay_ms=1000,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.commit()

    response = await ac.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["provider"] == "openrouter"
    assert data[0]["type"] == "llm"
    assert data[0]["status"] == "available"
