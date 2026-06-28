from fastapi import APIRouter
from sqlalchemy import text

from src.config.database import engine
from src.config.settings import get_settings
from src.services.key_health_check import get_key_health_summary

router = APIRouter()


@router.get("/health")
async def health_check():
    """Проверка здоровья сервиса."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "service": "API Hub",
        "version": get_settings().APP_VERSION,
        "database": db_status,
    }


@router.get("/health/keys")
async def health_check_keys():
    """Детальный health-check всех ключей: статусы, circuit breaker, ошибки."""
    try:
        summary = await get_key_health_summary()

        # Определяем общий статус
        statuses = summary.get("key_statuses", {})
        total = sum(statuses.values())
        ok_count = statuses.get("ok", 0)

        if total == 0:
            overall = "no_keys"
        elif ok_count == 0:
            overall = "critical"
        elif ok_count < total:
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "status": overall,
            "total_keys": total,
            "healthy_keys": ok_count,
            **summary,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "key_statuses": {},
            "circuit_breakers": {},
            "recent_errors_5m": 0,
        }
