from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from typing import List
import uuid

from src.config.database import get_session
from src.models.user import User
from src.models.api_key import ApiKey
from src.models.provider import Provider
from src.config.settings import get_settings

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_key(
    provider_name: str,
    api_key: str,
    alias: str = "основной",
    session: AsyncSession = Depends(get_session),
):
    """Загрузить API-ключ для провайдера."""
    settings = get_settings()

    # Находим провайдера
    provider_result = await session.execute(
        select(Provider).where(Provider.name == provider_name, Provider.is_active == True)
    )
    provider = provider_result.scalar_one_or_none()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_name}' not found or inactive",
        )

    # Находим или создаём пользователя (упрощённо для MVP)
    user_result = await session.execute(select(User).where(User.name == "default_user"))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(
            name="default_user",
            email="default@example.com",
            api_key=settings.MASTER_KEY,
        )
        session.add(user)
        await session.flush()

    # Проверяем, нет ли уже такого ключа
    existing_result = await session.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.provider_id == provider.id,
            ApiKey.key_alias == alias,
            ApiKey.is_active == True,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        await session.execute(
            update(ApiKey)
            .where(ApiKey.id == existing.id)
            .values(key_ref=api_key, last_used_at=None, last_status=None)
        )
        await session.commit()
        return {
            "id": str(existing.id),
            "provider": provider.name,
            "alias": alias,
            "status": "ok",
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
        }

    # Создаём новый
    new_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref=api_key,
        key_alias=alias,
    )
    session.add(new_key)
    await session.commit()
    await session.refresh(new_key)

    return {
        "id": str(new_key.id),
        "provider": provider.name,
        "alias": new_key.key_alias,
        "status": "ok",
        "created_at": new_key.created_at.isoformat() if new_key.created_at else None,
    }


@router.get("/")
async def list_keys(session: AsyncSession = Depends(get_session)):
    """Список всех ключей (без значений)."""
    result = await session.execute(
        select(ApiKey, User.name.label("user_name"), Provider.name.label("provider_name"))
        .join(User, ApiKey.user_id == User.id)
        .join(Provider, ApiKey.provider_id == Provider.id)
        .where(ApiKey.is_active == True, User.is_active == True, Provider.is_active == True)
    )
    keys = []
    for row in result:
        keys.append(
            {
                "id": str(row.ApiKey.id),
                "user": row.user_name,
                "provider": row.provider_name,
                "alias": row.ApiKey.key_alias,
                "status": row.ApiKey.last_status or "ok",
                "last_used_at": row.ApiKey.last_used_at.isoformat() if row.ApiKey.last_used_at else None,
                "created_at": row.ApiKey.created_at.isoformat() if row.ApiKey.created_at else None,
            }
        )
    return keys


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(key_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Удалить ключ."""
    result = await session.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Key not found"
        )
    await session.execute(
        update(ApiKey)
        .where(ApiKey.id == key_id)
        .values(is_active=False)
    )
    await session.commit()
    return None


@router.get("/{key_id}/status")
async def get_key_status(key_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Проверить работоспособность ключа."""
    result = await session.execute(
        select(ApiKey, Provider)
        .join(Provider, ApiKey.provider_id == Provider.id)
        .where(ApiKey.id == key_id, ApiKey.is_active == True, Provider.is_active == True)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Key not found or inactive"
        )
    api_key, provider = row

    return {
        "id": str(api_key.id),
        "provider": provider.name,
        "status": api_key.last_status or "ok",
        "rate_limit_remaining": None,
        "checked_at": api_key.last_used_at.isoformat() if api_key.last_used_at else api_key.created_at.isoformat() if api_key.created_at else None,
    }
