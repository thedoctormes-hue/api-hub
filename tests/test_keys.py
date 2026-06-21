"""Тесты для /keys роутов."""

import pytest
from src.models.user import User
from src.models.provider import Provider
from src.models.api_key import ApiKey


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_create_key_success(client):
    """Успешное создание ключа."""
    ac, session = client

    # Создаём провайдера и пользователя в тестовой БД
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
    await session.flush()

    user = User(
        name="default_user",
        email="default@example.com",
        api_key="test-master-key",
    )
    session.add(user)
    await session.commit()

    response = await ac.post(
        "/keys/",
        params={"provider_name": "openrouter", "api_key": "sk-test-123", "alias": "тестовый"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "openrouter"
    assert data["alias"] == "тестовый"
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_create_key_provider_not_found(client):
    """Создание ключа с несуществующим провайдером → 404."""
    ac, _ = client
    response = await ac.post(
        "/keys/",
        params={"provider_name": "nonexistent", "api_key": "sk-test"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_keys_empty(client):
    """Список ключей при пустой базе."""
    ac, _ = client
    response = await ac.get("/keys/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_keys_with_data(client):
    """Список ключей с данными."""
    ac, session = client

    provider = Provider(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()

    response = await ac.get("/keys/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["provider"] == "test_provider"
    assert data[0]["alias"] == "основной"


@pytest.mark.asyncio
async def test_delete_key_not_found(client):
    """Удаление несуществующего ключа → 404."""
    ac, _ = client
    import uuid
    response = await ac.delete(f"/keys/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_key_status_not_found(client):
    """Статус несуществующего ключа → 404."""
    ac, _ = client
    import uuid
    response = await ac.get(f"/keys/{uuid.uuid4()}/status")
    assert response.status_code == 404
