from fastapi import APIRouter, HTTPException
from src.config.settings import get_settings
from src.config.database import engine
import asyncio

router = APIRouter()


@router.get("/health")
async def health_check():
    """Проверка здоровья сервиса."""
    try:
        # Проверяем подключение к БД
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    # TODO: проверить Redis, Vault, внешние провайдеры
    return {
        "status": "ok",
        "service": "API Hub",
        "version": get_settings().APP_VERSION,
        "database": db_status,
    }
