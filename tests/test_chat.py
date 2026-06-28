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


@pytest.mark.asyncio
async def test_chat_completions_empty_messages(client):
    """Пустой массив messages — запрос уходит к провайдеру и обрабатывается."""
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

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "messages cannot be empty"}
    mock_response.text = "bad request"
    mock_response.raise_for_status.side_effect = Exception("400")

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
                "messages": []
            }
        )
        # Провайдер вернул ошибку → API Hub возвращает 502
        assert response.status_code == 502


@pytest.mark.asyncio
async def test_chat_completions_rate_limit_from_provider(client):
    """Провайдер возвращает 429 (rate limit) → API Hub возвращает 502."""
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

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.json.return_value = {"error": {"message": "rate limit exceeded", "type": "rate_limit"}}
    mock_response.text = "rate limited"
    mock_response.raise_for_status.side_effect = Exception("429 rate limited")

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
                "messages": [{"role": "user", "content": "test"}]
            }
        )
        assert response.status_code == 502
        data = response.json()
        assert "rate limit" in data["detail"].lower()


@pytest.mark.asyncio
async def test_chat_completions_no_llm_providers_only_other_types(client):
    """Нет LLM-провайдеров, но есть провайдеры других типов → 400."""
    ac, session = client

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key",
    )
    session.add(user)
    await session.flush()

    # Добавляем geocode-провайдер (не LLM)
    provider = Provider(
        name="dadata",
        type="geocode",
        base_url="https://dadata.example.com",
        auth_type="header",
        auth_key_name="Authorization",
        rate_limit=30,
        timeout_sec=10,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="some-ref",
        key_alias="основной",
    )
    session.add(api_key)
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
async def test_chat_completions_provider_timeout(client):
    """Таймаут провайдера → 502."""
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

    import httpx

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request.side_effect = httpx.TimeoutException("Connection timed out")
        MockClient.return_value = mock_client

        response = await ac.post(
            "/v1/chat/completions",
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": "test"}]
            }
        )
        assert response.status_code == 502


@pytest.mark.asyncio
async def test_chat_completions_header_auth_type(client):
    """Chat с провайдером auth_type=header."""
    ac, session = client

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key",
    )
    session.add(user)
    await session.flush()

    provider = Provider(
        name="custom_provider",
        type="llm",
        base_url="https://custom.example.com/v1",
        auth_type="header",
        auth_key_name="x-api-key",
        rate_limit=10,
        timeout_sec=30,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-custom-key",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test",
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
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
                "model": "custom/model",
                "messages": [{"role": "user", "content": "test"}]
            }
        )
        assert response.status_code == 200
        # Проверяем что заголовок передан правильно
        call_kwargs = mock_client.request.call_args
        assert call_kwargs[1]["headers"]["x-api-key"] == "sk-custom-key"


@pytest.mark.asyncio
async def test_chat_completions_query_param_auth(client):
    """Chat с провайдером auth_type=query_param."""
    ac, session = client

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key",
    )
    session.add(user)
    await session.flush()

    provider = Provider(
        name="query_provider",
        type="llm",
        base_url="https://query.example.com/v1",
        auth_type="query_param",
        auth_key_name="api_key",
        rate_limit=10,
        timeout_sec=30,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-query-key",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test",
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
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
                "model": "query/model",
                "messages": [{"role": "user", "content": "test"}]
            }
        )
        assert response.status_code == 200
        # Проверяем что api_key передан как query param
        call_kwargs = mock_client.request.call_args
        assert call_kwargs[1]["params"]["api_key"] == "sk-query-key"


@pytest.mark.asyncio
async def test_chat_completions_generic_exception(client):
    """Chat: generic исключение (не httpx) → 502."""
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
        mock_client.request.side_effect = RuntimeError("unexpected error")
        MockClient.return_value = mock_client

        response = await ac.post(
            "/v1/chat/completions",
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": "test"}]
            }
        )
        assert response.status_code == 502
        assert "unexpected error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_completions_success_with_meta(client):
    """Chat: успешный ответ содержит _meta с информацией о провайдере."""
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

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-test",
        "choices": [{"message": {"role": "assistant", "content": "Hello!"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
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
                "messages": [{"role": "user", "content": "test"}]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "_meta" in data
        assert data["_meta"]["provider"] == "openrouter"
        assert "latency_ms" in data["_meta"]
        assert data["_meta"]["fallback_used"] is False


@pytest.mark.asyncio
async def test_chat_completions_query_param_auth(client):
    """Chat: провайдер с query_param auth (Gemini) формирует правильный URL."""
    ac, session = client

    user = User(name="test_user", email="test@test.com", api_key="test-key")
    session.add(user)
    await session.flush()

    provider = Provider(
        name="gemini_test", type="llm",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        auth_type="query_param", auth_key_name="key",
        rate_limit=10, timeout_sec=30, retry_count=3, retry_delay_ms=1000, is_active=True,
    )
    session.add(provider)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id, provider_id=provider.id,
        key_ref="test-ref-gemini", key_alias="test",
    )
    session.add(api_key)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test", "choices": [{"message": {"role": "assistant", "content": "Hi"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request.return_value = mock_response
        MockClient.return_value = mock_client

        response = await ac.post("/v1/chat/completions",
            json={"model": "gemini-test", "messages": [{"role": "user", "content": "hi"}]})
        assert response.status_code == 200

        # Проверяем что ключ передан как query param
        call_args = mock_client.request.call_args
        assert call_args[1]["params"]["key"] == "test-ref-gemini"


@pytest.mark.asyncio
async def test_chat_completions_provider_http_error(client):
    """Chat: HTTPStatusError от провайдера → 502 с деталями ошибки."""
    ac, session = client

    user = User(name="test_user", email="test@test.com", api_key="test-key")
    session.add(user)
    await session.flush()

    provider = Provider(
        name="failing_provider", type="llm",
        base_url="https://fail.example.com/v1",
        auth_type="bearer", auth_key_name="Authorization",
        rate_limit=10, timeout_sec=30, retry_count=3, retry_delay_ms=1000, is_active=True,
    )
    session.add(provider)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id, provider_id=provider.id,
        key_ref="test-ref-fail", key_alias="test",
    )
    session.add(api_key)
    await session.commit()

    import httpx as httpx_mod
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limited"
    mock_response.json.return_value = {"error": "rate_limit_exceeded"}
    http_error = httpx_mod.HTTPStatusError("Rate limited", request=MagicMock(), response=mock_response)

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request.side_effect = http_error
        MockClient.return_value = mock_client

        response = await ac.post("/v1/chat/completions",
            json={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
        assert response.status_code == 502
        assert "429" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_completions_request_log_on_success(client):
    """Chat: при успехе создаётся RequestLog с токенами."""
    ac, session = client

    user = User(name="test_user", email="test@test.com", api_key="test-key")
    session.add(user)
    await session.flush()

    provider = Provider(
        name="log_test", type="llm",
        base_url="https://log.example.com/v1",
        auth_type="bearer", auth_key_name="Authorization",
        rate_limit=10, timeout_sec=30, retry_count=3, retry_delay_ms=1000, is_active=True,
    )
    session.add(provider)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id, provider_id=provider.id,
        key_ref="test-ref-log", key_alias="test",
    )
    session.add(api_key)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test", "choices": [{"message": {"role": "assistant", "content": "Hi"}}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 25},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request.return_value = mock_response
        MockClient.return_value = mock_client

        response = await ac.post("/v1/chat/completions",
            json={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
        assert response.status_code == 200

    # Проверяем что RequestLog создан
    from src.models.request_log import RequestLog
    from sqlalchemy import select, func
    result = await session.execute(select(func.count(RequestLog.id)))
    assert result.scalar_one() >= 1
