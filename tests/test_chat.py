"""Тесты для /v1/chat/completions роута."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.models.user import User
from src.models.provider import Provider
from src.models.api_key import ApiKey


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_chat_completions_no_users(client):
    """Chat completions без пользователей → 500."""
    ac, _ = client
    response = await ac.post(
        "/v1/chat/completions",
        json={
            "model": "openrouter/auto",
            "messages": [{"role": "user", "content": "test"}]
        }
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_chat_completions_no_keys(client):
    """Chat completions без активных ключей → 400."""
    ac, session = client

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key",
    )
    session.add(user)
    await session.commit()

    response = await ac.post(
        "/v1/chat/completions",
        json={
            "model": "openrouter/auto",
            "messages": [{"role": "user", "content": "test"}]
        }
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_completions_success(client):
    """Успешный chat completions через провайдера."""
    ac, session = client

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key",
    )
    session.add(user)
    await session.flush()

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

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()

    # Мокаем httpx клиент
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Привет!"},
                "finish_reason": "stop"
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request.return_value = mock_response
        MockClient.return_value = mock_client

        response = await ac.post(
            "/v1/chat/completions",
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": "Привет!"}]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "chatcmpl-test"
        assert data["_meta"]["provider"] == "openrouter"
        assert data["_meta"]["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_chat_completions_provider_error(client):
    """Ошибка от провайдера → 502."""
    ac, session = client

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key",
    )
    session.add(user)
    await session.flush()

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

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "rate limited"}
        mock_response.text = "rate limited"
        mock_response.raise_for_status.side_effect = Exception("429")
        mock_client.request.return_value = mock_response
        MockClient.return_value = mock_client

        response = await ac.post(
            "/v1/chat/completions",
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": "test"}]
            }
        )
        assert response.status_code == 502
