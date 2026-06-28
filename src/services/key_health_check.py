"""Сервис проверки здоровья API-ключей.

Реализует алгоритм из antcat/plans/key-verification-system.md:
- Health-check через /models или /health эндпоинты
- Circuit breaker (3 ошибки → open → cooldown → half-open)
- Логирование в key_health_log
- Метрики для Prometheus
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import async_session
from src.models.api_key import ApiKey
from src.models.circuit_breaker import CircuitBreaker
from src.models.key_health_log import KeyHealthLog

logger = logging.getLogger(__name__)

# Интервалы health-check по типам провайдеров (секунды)
HEALTH_CHECK_INTERVALS = {
    "llm": 30,
    "search": 300,
    "ocr": 600,
    "tts": 600,
    "image": 120,
    "agent": 120,
    "geocode": 300,
    "validate": 300,
    "scrape": 120,
    "generate": 120,
}

# Circuit breaker пороги
FAIL_THRESHOLD = 3
COOLDOWN_SECONDS = 300  # 5 минут


async def _get_circuit_breaker(session: AsyncSession, api_key_id, provider_id) -> CircuitBreaker | None:
    """Получить или создать circuit breaker для ключа."""
    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.api_key_id == api_key_id)
    )
    cb = result.scalar_one_or_none()
    if not cb:
        cb = CircuitBreaker(api_key_id=api_key_id, provider_id=provider_id)
        session.add(cb)
        await session.flush()
    return cb


async def _log_health_check(
    session: AsyncSession,
    api_key_id,
    status: str,
    latency_ms: int,
    error_text: str | None = None,
):
    """Записать результат health-check в key_health_log."""
    entry = KeyHealthLog(
        api_key_id=api_key_id,
        status=status,
        latency_ms=latency_ms,
        error_text=error_text,
    )
    session.add(entry)


async def check_key_health(session: AsyncSession, api_key: ApiKey) -> dict:
    """Проверить здоровье одного ключа. Возвращает dict с status, latency_ms."""
    from src.models.provider import Provider
    result = await session.execute(
        select(Provider).where(Provider.id == api_key.provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        return {"status": "error", "latency_ms": 0, "error_text": "Provider not found"}

    # Circuit breaker check
    cb_record = await _get_circuit_breaker(session, api_key.id, api_key.provider_id)

    if cb_record and cb_record.state == "open":
        if cb_record.opened_at:
            elapsed = (datetime.now(timezone.utc) - cb_record.opened_at).total_seconds()
            if elapsed < COOLDOWN_SECONDS:
                remaining = COOLDOWN_SECONDS - elapsed
                logger.debug(f"Key {api_key.key_alias}: circuit open, cooldown {remaining:.0f}s")
                return {
                    "status": "circuit_open",
                    "latency_ms": 0,
                    "error_text": f"Cooldown {remaining:.0f}s remaining",
                }
            else:
                cb_record.state = "half-open"
                cb_record.half_open_at = datetime.now(timezone.utc)
                await session.flush()
                logger.info(f"Key {api_key.key_alias}: circuit breaker -> half-open")

    # Проверяем ключ
    api_key_value = await resolve_key_from_vault(api_key.key_ref)
    if not api_key_value:
        logger.warning(f"Key {api_key.key_alias}: empty key value from vault")
        await _log_health_check(session, api_key.id, "error", 0, "Empty key value")
        await session.commit()
        return {"status": "error", "latency_ms": 0, "error_text": "Empty key value"}

    base_url = provider.base_url.rstrip("/")
    # Если у провайза задан кастомный health endpoint — используем его
    if hasattr(provider, 'health_check_endpoint') and provider.health_check_endpoint:
        health_endpoint = provider.health_check_endpoint
    else:
        health_endpoint = "/models" if provider.type == "llm" else "/health"
    url = f"{base_url}{health_endpoint}"

    headers = {}
    params = {}
    if provider.auth_type == "bearer":
        headers["Authorization"] = f"Bearer {api_key_value}"
    elif provider.auth_type == "header":
        headers[provider.auth_key_name] = api_key_value
    elif provider.auth_type == "query_param":
        params[provider.auth_key_name] = api_key_value

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            start = datetime.now(timezone.utc)
            response = await client.get(url, headers=headers, params=params)
            latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        status = "ok" if response.status_code < 400 else "error"
        if response.status_code == 429:
            status = "rate_limited"

        await _update_circuit_breaker(session, api_key.id, api_key.provider_id, status == "ok")

        api_key.last_status = status
        api_key.verified_at = datetime.now(timezone.utc)

        error_text = None if status == "ok" else f"HTTP {response.status_code}"
        await _log_health_check(session, api_key.id, status, latency_ms, error_text)
        await session.commit()

        logger.debug(f"Key {api_key.key_alias}: {status} ({latency_ms}ms)")
        return {"status": status, "latency_ms": latency_ms}

    except httpx.TimeoutException:
        await _update_circuit_breaker(session, api_key.id, api_key.provider_id, False)
        await _log_health_check(session, api_key.id, "timeout", 10000, "Request timeout")
        await session.commit()
        logger.warning(f"Key {api_key.key_alias}: timeout")
        return {"status": "timeout", "latency_ms": 10000, "error_text": "Request timeout"}
    except httpx.ConnectError as e:
        await _update_circuit_breaker(session, api_key.id, api_key.provider_id, False)
        await _log_health_check(session, api_key.id, "error", 0, f"Connection error: {str(e)[:200]}")
        await session.commit()
        logger.warning(f"Key {api_key.key_alias}: connection error — {e}")
        return {"status": "error", "latency_ms": 0, "error_text": f"Connection error: {str(e)[:200]}"}
    except Exception as e:
        await _update_circuit_breaker(session, api_key.id, api_key.provider_id, False)
        await _log_health_check(session, api_key.id, "error", 0, str(e)[:255])
        await session.commit()
        logger.error(f"Key {api_key.key_alias}: unexpected error — {e}")
        return {"status": "error", "latency_ms": 0, "error_text": str(e)[:255]}


async def _update_circuit_breaker(session: AsyncSession, api_key_id, provider_id, success: bool):
    """Обновить состояние circuit breaker."""
    cb = await _get_circuit_breaker(session, api_key_id, provider_id)
    now = datetime.now(timezone.utc)

    if success:
        if cb.state != "closed":
            logger.info(f"Key {api_key_id}: circuit breaker -> closed")
        cb.state = "closed"
        cb.fail_count = 0
        cb.last_success = now
    else:
        cb.fail_count += 1
        cb.last_failure = now
        if cb.fail_count >= FAIL_THRESHOLD:
            cb.state = "open"
            cb.opened_at = now
            logger.warning(
                f"Key {api_key_id}: circuit breaker -> open "
                f"(fail_count={cb.fail_count}, cooldown={COOLDOWN_SECONDS}s)"
            )


async def resolve_key_from_vault(key_ref: str) -> str:
    """Получить значение ключа из Vault по SHA-256 хешу."""
    import json
    import pathlib

    backup = pathlib.Path("/root/LabDoctorM/vault/free-api-hunter/secrets-backup.json")
    if backup.exists():
        try:
            data = json.loads(backup.read_text())
            values = data.get("values", data)
            if isinstance(values, dict):
                for full_key, meta in values.items():
                    if isinstance(meta, str) and hash_key(meta) == key_ref:
                        return meta
                    if isinstance(meta, dict):
                        value = meta.get("value") or meta.get("apiKey")
                        if value and hash_key(value) == key_ref:
                            return value
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read vault backup: {e}")
    return ""


def hash_key(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()


async def run_health_check_cycle():
    """Один цикл проверки всех активных ключей."""
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.is_active)
        )
        keys = result.scalars().all()

        logger.info(f"Starting health check for {len(keys)} keys")

        ok_count = 0
        error_count = 0
        timeout_count = 0
        circuit_open_count = 0

        for key in keys:
            try:
                health = await check_key_health(session, key)
                status = health["status"]
                if status == "ok":
                    ok_count += 1
                elif status == "timeout":
                    timeout_count += 1
                elif status == "circuit_open":
                    circuit_open_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Health check failed for {key.key_alias}: {e}")

        logger.info(
            f"Health check cycle complete: "
            f"ok={ok_count}, error={error_count}, timeout={timeout_count}, "
            f"circuit_open={circuit_open_count}"
        )
        return {
            "total": len(keys),
            "ok": ok_count,
            "error": error_count,
            "timeout": timeout_count,
            "circuit_open": circuit_open_count,
        }


async def get_key_health_summary() -> dict:
    """Получить сводку по здоровью ключей (для health endpoint)."""
    async with async_session() as session:
        # Статусы ключей
        result = await session.execute(
            select(ApiKey.last_status, func.count(ApiKey.id))
            .where(ApiKey.is_active)
            .group_by(ApiKey.last_status)
        )
        statuses = {status or "unknown": count for status, count in result.all()}

        # Circuit breaker
        result = await session.execute(
            select(CircuitBreaker.state, func.count(CircuitBreaker.id))
            .group_by(CircuitBreaker.state)
        )
        cb_states = {state: count for state, count in result.all()}

        # Последние ошибки (последние 5 минут)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = await session.execute(
            select(func.count(KeyHealthLog.id))
            .where(
                KeyHealthLog.checked_at >= cutoff,
                KeyHealthLog.status.in_(["error", "timeout"]),
            )
        )
        recent_errors = result.scalar_one()

        return {
            "key_statuses": statuses,
            "circuit_breakers": cb_states,
            "recent_errors_5m": recent_errors,
        }
