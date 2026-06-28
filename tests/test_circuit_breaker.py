"""Тесты для src/models/circuit_breaker.py."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select

from src.models.circuit_breaker import CircuitBreaker
from src.models.api_key import ApiKey
from src.models.provider import Provider
from src.models.user import User


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_provider(session=None):
    provider = Provider(
        name="test_cb_provider",
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
    return provider


def _make_user(session):
    import uuid
    user = User(
        name=f"cb_test_user_{uuid.uuid4().hex[:8]}",
        email=f"cb_test_{uuid.uuid4().hex[:8]}@example.com",
        api_key=f"cb-test-key-{uuid.uuid4().hex[:8]}",
    )
    session.add(user)
    return user


def _make_api_key(provider_id, user_id):
    return ApiKey(
        user_id=user_id,
        provider_id=provider_id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )


# --- Создание ---

@pytest.mark.asyncio
async def test_circuit_breaker_default_state(client):
    """CircuitBreaker по умолчанию в состоянии closed."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
    )
    session.add(cb)
    await session.commit()

    assert cb.state == "closed"
    assert cb.fail_count == 0
    assert cb.last_failure is None
    assert cb.last_success is None
    assert cb.opened_at is None
    assert cb.half_open_at is None


@pytest.mark.asyncio
async def test_circuit_breaker_has_uuid(client):
    """CircuitBreaker имеет UUID primary key."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
    )
    session.add(cb)
    await session.commit()

    assert cb.id is not None


@pytest.mark.asyncio
async def test_circuit_breaker_custom_state(client):
    """CircuitBreaker можно создать с кастомным состоянием."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="open",
        fail_count=5,
        opened_at=datetime.now(timezone.utc),
    )
    session.add(cb)
    await session.commit()

    assert cb.state == "open"
    assert cb.fail_count == 5
    assert cb.opened_at is not None


# --- Переходы состояний ---

@pytest.mark.asyncio
async def test_circuit_breaker_closed_to_open(client):
    """CircuitBreaker переходит из closed в open при накоплении ошибок."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="closed",
        fail_count=0,
    )
    session.add(cb)
    await session.commit()

    # Симулируем ошибки
    for i in range(3):
        cb.fail_count += 1
        cb.last_failure = datetime.now(timezone.utc)
        if cb.fail_count >= 3:
            cb.state = "open"
            cb.opened_at = datetime.now(timezone.utc)

    await session.commit()

    assert cb.state == "open"
    assert cb.fail_count == 3
    assert cb.opened_at is not None


@pytest.mark.asyncio
async def test_circuit_breaker_open_to_half_open(client):
    """CircuitBreaker переходит из open в half-open."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="open",
        fail_count=3,
        opened_at=datetime.now(timezone.utc),
    )
    session.add(cb)
    await session.commit()

    cb.state = "half-open"
    cb.half_open_at = datetime.now(timezone.utc)
    await session.commit()

    assert cb.state == "half-open"
    assert cb.half_open_at is not None


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_to_closed(client):
    """CircuitBreaker переходит из half-open в closed при успехе."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="half-open",
        fail_count=3,
        half_open_at=datetime.now(timezone.utc),
    )
    session.add(cb)
    await session.commit()

    cb.state = "closed"
    cb.fail_count = 0
    cb.last_success = datetime.now(timezone.utc)
    await session.commit()

    assert cb.state == "closed"
    assert cb.fail_count == 0
    assert cb.last_success is not None


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_to_open(client):
    """CircuitBreaker возвращается в open при ошибке в half-open."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="half-open",
        fail_count=3,
        half_open_at=datetime.now(timezone.utc),
    )
    session.add(cb)
    await session.commit()

    cb.state = "open"
    cb.fail_count += 1
    cb.last_failure = datetime.now(timezone.utc)
    cb.opened_at = datetime.now(timezone.utc)
    await session.commit()

    assert cb.state == "open"
    assert cb.fail_count == 4


# --- Граничные случаи ---

@pytest.mark.asyncio
async def test_circuit_breaker_fail_count_zero(client):
    """CircuitBreaker с fail_count=0 остаётся closed."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="closed",
        fail_count=0,
    )
    session.add(cb)
    await session.commit()

    assert cb.state == "closed"
    assert cb.fail_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_state_values(client):
    """CircuitBreaker поддерживает три допустимых состояния."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    for state in ("closed", "open", "half-open"):
        cb = CircuitBreaker(
            api_key_id=api_key.id,
            provider_id=provider.id,
            state=state,
        )
        session.add(cb)
        await session.flush()
        assert cb.state == state


@pytest.mark.asyncio
async def test_circuit_breaker_queryable(client):
    """CircuitBreaker можно запросить из БД по api_key_id."""
    ac, session = client

    provider = _make_provider()
    session.add(provider)
    await session.flush()

    user = _make_user(session)
    await session.flush()

    api_key = _make_api_key(provider.id, user.id)
    session.add(api_key)
    await session.flush()

    cb = CircuitBreaker(
        api_key_id=api_key.id,
        provider_id=provider.id,
        state="open",
        fail_count=5,
    )
    session.add(cb)
    await session.commit()

    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.api_key_id == api_key.id)
    )
    found = result.scalar_one_or_none()
    assert found is not None
    assert found.state == "open"
    assert found.fail_count == 5
