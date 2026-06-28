"""Сервис проверки здоровья API-ключей.

Реализует алгоритм из antcat/plans/key-verification-system.md:
- Health-check через /models или /health эндпоинты
- Circuit breaker (3 ошибки → open → cooldown → half-open)
- Логирование в key_health_log
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import async_session
from src.models.api_key import ApiKey
from src.models.circuit_breaker import CircuitBreaker

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


async def check_key_health(session: AsyncSession, api_key: ApiKey) -> dict:
    """Проверить здоровье одного ключа. Возвращает dict с status, latency_ms."""
    # Получаем провайдера
    from src.models.provider import Provider
    result = await session.execute(
        select(Provider).where(Provider.id == api_key.provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        return {"status": "error", "latency_ms": 0, "error_text": "Provider not found"}

    # Проверяем circuit breaker
    cb = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.api_key_id == api_key.id)
    )
    cb_record = cb.scalar_one_or_none()

    if cb_record and cb_record.state == "open":
        # Проверяем cooldown
        if cb_record.opened_at:
            elapsed = (datetime.now(timezone.utc) - cb_record.opened_at).total_seconds()
            if elapsed < COOLDOWN_SECONDS:
                return {"status": "circuit_open", "latency_ms": 0, "error_text": f"Cooldown {COOLDOWN_SECONDS - elapsed:.0f}s remaining"}
            else:
                # Переход в half-open
                cb_record.state = "half-open"
                cb_record.half_open_at = datetime.now(timezone.utc)
                await session.flush()

    # Пробуем запрос к провайдеру
    try:
        base_url = provider.base_url.rstrip("/")
        health_endpoint = "/models" if provider.type == "llm" else "/health"
        url = f"{base_url}{health_endpoint}"

        # Загружаем ключ из vault (через key_ref)
        # В проде — обращение к Vault API. Для теста — placeholder
        api_key_value = await resolve_key_from_vault(api_key.key_ref)

        headers = {}
        if provider.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {api_key_value}"
        elif provider.auth_type == "header":
            headers[provider.auth_key_name] = api_key_value

        async with httpx.AsyncClient(timeout=10) as client:
            start = datetime.now(timezone.utc)
            response = await client.get(url, headers=headers)
            latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        status = "ok" if response.status_code < 400 else "error"
        if response.status_code == 429:
            status = "rate_limited"

        # Обновляем circuit breaker
        await _update_circuit_breaker(session, api_key.id, api_key.provider_id, status == "ok")

        # Обновляем статус ключа
        api_key.last_status = status
        api_key.verified_at = datetime.now(timezone.utc)

        # Логируем
        log_entry = {
            "api_key_id": api_key.id,
            "status": status,
            "latency_ms": latency_ms,
            "error_text": None if status == "ok" else f"HTTP {response.status_code}",
        }
        from src.models.key_health_log import KeyHealthLog
        session.add(KeyHealthLog(**log_entry))

        await session.commit()
        return {"status": status, "latency_ms": latency_ms}

    except httpx.TimeoutException:
        await _update_circuit_breaker(session, api_key.id, api_key.provider_id, False)
        await session.commit()
        return {"status": "timeout", "latency_ms": 10000, "error_text": "Request timeout"}
    except Exception as e:
        await _update_circuit_breaker(session, api_key.id, api_key.provider_id, False)
        await session.commit()
        return {"status": "error", "latency_ms": 0, "error_text": str(e)[:255]}


async def _update_circuit_breaker(session: AsyncSession, api_key_id, provider_id, success: bool):
    """Обновить состояние circuit breaker"""
    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.api_key_id == api_key_id)
    )
    cb = result.scalar_one_or_none()

    if not cb:
        cb = CircuitBreaker(api_key_id=api_key_id, provider_id=provider_id)
        session.add(cb)
        await session.flush()

    now = datetime.now(timezone.utc)

    if success:
        cb.state = "closed"
        cb.fail_count = 0
        cb.last_success = now
    else:
        cb.fail_count += 1
        cb.last_failure = now
        if cb.fail_count >= FAIL_THRESHOLD:
            cb.state = "open"
            cb.opened_at = now


async def resolve_key_from_vault(key_ref: str) -> str:
    """Получить значение ключа из Vault по SHA-256 хешу.
    В проде — обращение к Vault API.
    Для теста — читаем из secrets-backup.json.
    """
    import json
    import pathlib

    backup = pathlib.Path("/root/LabDoctorM/vault/free-api-hunter/secrets-backup.json")
    if backup.exists():
        data = json.loads(backup.read_text())
        # Формат: {"provider/key": "value", ...} или {"values": {...}}
        values = data.get("values", data)
        if isinstance(values, dict):
            for full_key, meta in values.items():
                if isinstance(meta, str) and hash_key(meta) == key_ref:
                    return meta
                if isinstance(meta, dict):
                    value = meta.get("value") or meta.get("apiKey")
                    if value and hash_key(value) == key_ref:
                        return value
    return ""


def hash_key(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()


async def run_health_check_cycle():
    """Один цикл проверки всех активных ключей"""
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.is_active == True)
        )
        keys = result.scalars().all()

        logger.info(f"Starting health check for {len(keys)} keys")
        for key in keys:
            try:
                health = await check_key_health(session, key)
                logger.debug(f"Key {key.key_alias}: {health['status']} ({health['latency_ms']}ms)")
            except Exception as e:
                logger.error(f"Health check failed for {key.key_alias}: {e}")

        logger.info("Health check cycle complete")
