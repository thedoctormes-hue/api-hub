#!/usr/bin/env python3
"""
Импорт бесплатных ключей из JSON (stdout export_free_keys.py) в PostgreSQL api-hub.
Использует SQLAlchemy async.

Usage:
  python scripts/export_free_keys.py > /tmp/free_keys.json
  python scripts/import_free_keys.py --db postgresql+asyncpg://apihub:apihub@localhost/apihub

Ключи НЕ записываются напрямую в БД — только ссылки (key_ref) на vault.
Оригинальные ключи остаются в vault (OpenClaw secrets management).
"""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Добавляем путь к проекту
sys.path.insert(0, "/root/LabDoctorM/projects/api-hub")

from src.models.provider import Provider
from src.models.api_key import ApiKey
from src.config.database import Base

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def get_or_create_provider(session: AsyncSession, name: str, base_url: str = "") -> Provider:
    """Получить или создать провайдера"""
    result = await session.execute(select(Provider).where(Provider.name == name))
    provider = result.scalar_one_or_none()
    if provider:
        return provider

    # Создаём нового провайдера
    provider_type = "llm"
    auth_type = "bearer"
    auth_key_name = "Authorization"

    # Маппинг типов
    type_map = {
        "ocrspace": ("ocr", "query_param", "apikey"),
        "dadata": ("geocode", "header", "X-API-Key"),
        "abstractapi": ("validate", "query_param", "api_key"),
        "scraperapi": ("scrape", "query_param", "api_key"),
        "pdfgeneratorapi": ("generate", "bearer", "Authorization"),
        "tavily": ("search", "body", "api_key"),
        "firecrawl": ("search", "bearer", "Authorization"),
        "tinyfish": ("search", "bearer", "Authorization"),
        "pollinations": ("image", "query_param", ""),
    }

    if name in type_map:
        provider_type, auth_type, auth_key_name = type_map[name]

    provider = Provider(
        name=name,
        type=provider_type,
        base_url=base_url or f"https://api.{name}.com",
        auth_type=auth_type,
        auth_key_name=auth_key_name,
        rate_limit=100,
        is_active=True,
        is_free=True,
        free_source="free_api_hunter",
    )
    session.add(provider)
    await session.flush()
    logger.info(f"Created provider: {name} (type={provider_type})")
    return provider


def hash_key(key: str) -> str:
    """SHA-256 хеш ключа для хранения в БД (не сам ключ!)"""
    return hashlib.sha256(key.encode()).hexdigest()


async def import_keys(db_uri: str, keys_file: str):
    """Основная функция импорта"""
    engine = create_async_engine(db_uri, echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Создаём таблицы если не существуют
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Создаём системного пользователя если не существует
    from src.models.user import User
    async with async_session() as session:
        existing = await session.execute(
            select(User).where(User.id == "00000000-0000-0000-0000-000000000000")
        )
        if not existing.scalar_one_or_none():
            session.add(User(
                id="00000000-0000-0000-0000-000000000000",
                name="system",
                api_key="sys-internal-key",
            ))
            await session.commit()
            logger.info("Created system user")

    with open(keys_file, "r") as f:
        keys_data = json.load(f)

    async with async_session() as session:
        imported = 0
        skipped = 0

        for key_entry in keys_data:
            provider_name = key_entry["provider"]
            key_value = key_entry["key"]
            alias = key_entry.get("alias", "основной")
            source = key_entry.get("source", "free_api_hunter")
            rate_limit_type = key_entry.get("rate_limit_type", "unknown")

            # Пропускаем мусор (lock-файлы и т.п.)
            if len(key_value) < 10 or key_value.startswith("{") or key_value.startswith("["):
                logger.warning(f"Skipping invalid key: {alias}")
                skipped += 1
                continue

            # Получаем или создаём провайдера
            provider = await get_or_create_provider(session, provider_name)

            # Проверяем дубликат по хешу
            key_hash = hash_key(key_value)
            existing = await session.execute(
                select(ApiKey).where(
                    ApiKey.key_ref == key_hash,
                    ApiKey.provider_id == provider.id,
                )
            )
            if existing.scalar_one_or_none():
                logger.info(f"Skipping duplicate: {provider_name}/{alias}")
                skipped += 1
                continue

            # Системный пользователь (всегда существует после seed)
            system_user_id = "00000000-0000-0000-0000-000000000000"

            # Создаём ApiKey
            api_key = ApiKey(
                user_id=system_user_id,
                provider_id=provider.id,
                key_ref=key_hash,
                key_alias=alias,
                source="free_api_hunter",
                verified_at=datetime.now(timezone.utc),
                rate_limit_type=rate_limit_type,
                is_active=True,
                last_status="ok",
            )
            session.add(api_key)
            imported += 1
            logger.info(f"Imported: {provider_name}/{alias}")

        await session.commit()
        logger.info(f"\nDone: {imported} imported, {skipped} skipped")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import free API keys into api-hub database")
    parser.add_argument("--db", required=True, help="PostgreSQL URI (postgresql+asyncpg://...)")
    parser.add_argument("--keys", default="/tmp/free_keys.json", help="Path to JSON keys file")
    args = parser.parse_args()

    asyncio.run(import_keys(args.db, args.keys))
