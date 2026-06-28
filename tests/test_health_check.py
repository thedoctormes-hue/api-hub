"""Тесты для src/services/key_health_check.py."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from src.services.key_health_check import (
    check_key_health,
    _update_circuit_breaker,
    hash_key,
    resolve_key_from_vault,
    run_health_check_cycle,
    FAIL_THRESHOLD,
    COOLDOWN_SECONDS,
)
from src.models.api_key import ApiKey
from src.models.provider import Provider
from src.models.circuit_breaker import CircuitBreaker
from src.models.key_health_log import KeyHealthLog
from src.models.user import User


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_provider(**overrides):
    defaults = dict(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com/v1",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=20,
        timeout_sec=30,
        retry_count=3,
        retry_delay_ms=1000,
        is_active=True,
        config=None,
    )
    defaults.update(overrides)
    return Provider(**defaults)


def _make_user(session):
    import uuid
    user = User(
        name=f"hc_test_user_{uuid.uuid4().hex[:8]}",
        email=f"hc_test_{uuid.uuid4().hex[:8]}@example.com",
        api_key=f"hc-test-key-{uuid.uuid4().hex[:8]}",
    )
    session.add(user)
    return user


def _make_api_key(session, provider_id, user_id, **overrides):
    defaults = dict(
        user_id=user_id,
        provider_id=provider_id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )
    defaults.update(overrides)
    api_key = ApiKey(**defaults)
    session.add(api_key)
    return api_key


# --- hash_key ---

def test_hash_key_deterministic():
    """hash_key детерминирован для одного и того же входа."""
    assert hash_key("abc") == hash_key("abc")


def test_hash_key_different_inputs():
    """hash_key даёт разные хеши для разных входов."""
    assert hash_key("key1") != hash_key("key2")


def test_hash_key_sha256():
    """hash_key использует SHA-256 (64 hex символа)."""
    result = hash_key("test")
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


# --- resolve_key_from_vault ---

def test_resolve_key_from_vault_no_file():
    """resolve_key_from_vault возвращает пустую строку если файл отсутствует."""
    # Файл /root/LabDoctorM/vault/free-api-hunter/secrets-backup.json
    # может не существовать в тестовом окружении. Проверяем что функция
    # не падает и возвращает пустую строку.
    import asyncio
    result = asyncio.run(resolve_key_from_vault("nonexistent-ref-12345"))
    # Если файл существует — ищем несуществующий хеш, вернёт ""
    # Если файл не существует — тоже вернёт ""
    assert result == ""


# --- check_key_health ---

@pytest.mark.asyncio
async def test_check_key_health_provider_not_found(client):
    """check_key_health возвращает error если провайдер не найден."""
    ac, session = client

    user = _make_user(session)
    await session.flush()

    import uuid
    # Создаём ключ с несуществующим provider_id (валидный UUID, но нет в БД)
    fake_provider_id = uuid.uuid4()
    api_key = _make_api_key(session, provider_id=fake_provider_id, user_id=user.id)
    await session.commit()

    result = await check_key_health(session, api_key)
    assert result["status"] == "error"
    assert "Provider not found" in result["error_text"]


@pytest.mark.asyncio
async def test_check_key_health_circuit_open_in_cooldown(client):
    """check_key_health возвращает circuit_open если cooldown не истёк."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="open",
        opened_at=datetime.now(timezone.utc) - timedelta(seconds=10),
    )
    session.add(cb)
    await session.commit()

    result = await check_key_health(session, api_key)
    assert result["status"] == "circuit_open"
    assert "Cooldown" in result["error_text"]


@pytest.mark.asyncio
async def test_check_key_health_circuit_open_cooldown_expired(client):
    """check_key_health переводит в half-open если cooldown истёк."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="open",
        opened_at=datetime.now(timezone.utc) - timedelta(seconds=COOLDOWN_SECONDS + 10),
    )
    session.add(cb)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_check_key_health_success(client):
    """check_key_health возвращает ok при успешном ответе."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "ok"
        assert result["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_check_key_health_rate_limited(client):
    """check_key_health возвращает rate_limited при 429."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 429

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "rate_limited"


@pytest.mark.asyncio
async def test_check_key_health_timeout(client):
    """check_key_health возвращает timeout при httpx.TimeoutException."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    import httpx

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "timeout"
        assert result["latency_ms"] == 10000


@pytest.mark.asyncio
async def test_check_key_health_generic_error(client):
    """check_key_health возвращает error при generic исключении."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = ConnectionError("connection refused")
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "error"
        assert "connection refused" in result["error_text"]


@pytest.mark.asyncio
async def test_check_key_health_creates_health_log(client):
    """check_key_health создаёт запись в key_health_log."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        await check_key_health(session, api_key)

    from sqlalchemy import select
    result = await session.execute(
        select(KeyHealthLog).where(KeyHealthLog.api_key_id == api_key.id)
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.status == "ok"


@pytest.mark.asyncio
async def test_check_key_health_non_llm_provider(client):
    """check_key_health использует /health для non-LLM провайдеров."""
    ac, session = client

    provider = _make_provider(type="geocode", base_url="https://dadata.example.com")
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "ok"
        call_args = mock_client.get.call_args
        assert "/health" in call_args[0][0]


# --- _update_circuit_breaker ---

@pytest.mark.asyncio
async def test_update_circuit_breaker_creates_new(client):
    """_update_circuit_breaker создаёт новый CircuitBreaker если не существует."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    await _update_circuit_breaker(session, api_key.id, provider.id, True)

    from sqlalchemy import select
    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.api_key_id == api_key.id)
    )
    cb = result.scalar_one_or_none()
    assert cb is not None
    assert cb.state == "closed"
    assert cb.fail_count == 0


@pytest.mark.asyncio
async def test_update_circuit_breaker_opens_after_threshold(client):
    """Circuit breaker открывается после FAIL_THRESHOLD ошибок."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    for _ in range(FAIL_THRESHOLD):
        await _update_circuit_breaker(session, api_key.id, provider.id, False)

    from sqlalchemy import select
    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.api_key_id == api_key.id)
    )
    cb = result.scalar_one_or_none()
    assert cb.state == "open"
    assert cb.fail_count == FAIL_THRESHOLD
    assert cb.opened_at is not None


@pytest.mark.asyncio
async def test_update_circuit_breaker_resets_on_success(client):
    """Circuit breaker сбрасывается при успехе после ошибок."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    await _update_circuit_breaker(session, api_key.id, provider.id, False)
    await _update_circuit_breaker(session, api_key.id, provider.id, False)
    await _update_circuit_breaker(session, api_key.id, provider.id, True)

    from sqlalchemy import select
    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.api_key_id == api_key.id)
    )
    cb = result.scalar_one_or_none()
    assert cb.state == "closed"
    assert cb.fail_count == 0
    assert cb.last_success is not None


@pytest.mark.asyncio
async def test_update_circuit_breaker_half_open_transitions(client):
    """Circuit breaker в half-open закрывается при успехе."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="half-open",
        fail_count=FAIL_THRESHOLD,
    )
    session.add(cb)
    await session.commit()

    await _update_circuit_breaker(session, api_key.id, provider.id, True)

    from sqlalchemy import select
    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.api_key_id == api_key.id)
    )
    cb_after = result.scalar_one_or_none()
    assert cb_after.state == "closed"
    assert cb_after.fail_count == 0


# --- run_health_check_cycle ---

@pytest.mark.asyncio
async def test_run_health_check_cycle_no_keys():
    """run_health_check_cycle корректно обрабатывает пустой список ключей."""
    with patch("src.services.key_health_check.async_session") as MockSession:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        MockSession.return_value = mock_session

        await run_health_check_cycle()


@pytest.mark.asyncio
async def test_check_key_health_empty_key_value(client):
    """check_key_health возвращает error если ключ пустой (не найден в vault)."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    with patch.object(
        __import__("src.services.key_health_check", fromlist=["resolve_key_from_vault"]),
        "resolve_key_from_vault",
        new_callable=AsyncMock,
        return_value=""
    ):
        result = await check_key_health(session, api_key)
        assert result["status"] == "error"
        assert "Empty key" in result["error_text"]


@pytest.mark.asyncio
async def test_check_key_health_half_open_accumulates_errors(client):
    """check_key_health: half-open + ошибки накапливаются до FAIL_THRESHOLD → open."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.flush()

    cb = CircuitBreaker(api_key_id=api_key.id, provider_id=provider.id, state="half-open")
    session.add(cb)
    await session.commit()

    import httpx

    # Необходимо FAIL_THRESHOLD ошибок чтобы перейти в open
    for i in range(FAIL_THRESHOLD):
        with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
             patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            MockClient.return_value = mock_client

            await session.refresh(cb)
            result = await check_key_health(session, api_key)
            assert result["status"] == "timeout"

    # После FAIL_THRESHOLD ошибок circuit breaker должен быть open
    await session.refresh(cb)
    assert cb.state == "open"


@pytest.mark.asyncio
async def test_check_key_health_all_statuses_error_above_400(client):
    """check_key_health: HTTP 500 статус → error."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "error"


@pytest.mark.asyncio
async def test_check_key_health_header_auth_type(client):
    """check_key_health использует header auth для провайдеров с auth_type=header."""
    ac, session = client

    provider = _make_provider(auth_type="header", auth_key_name="x-api-key")
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "ok"
        call_kwargs = mock_client.get.call_args
        assert "x-api-key" in call_kwargs[1]["headers"]


@pytest.mark.asyncio
async def test_check_key_health_bad_json_response(client):
    """check_key_health: HTTP 200 с плохим JSON → всё равно ok (только status_code)."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(session, provider_id=provider.id, user_id=user.id)
    await session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("src.services.key_health_check.httpx.AsyncClient") as MockClient, \
         patch("src.services.key_health_check.resolve_key_from_vault", new_callable=AsyncMock, return_value="test-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        result = await check_key_health(session, api_key)
        assert result["status"] == "ok"
        # Проверяем что api_key обновился
        assert api_key.last_status == "ok"
        assert api_key.verified_at is not None
