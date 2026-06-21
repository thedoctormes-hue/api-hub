from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_session
from src.models.provider import Provider

router = APIRouter()


@router.get("/models")
async def list_models(session: AsyncSession = Depends(get_session)):
    """Список доступных моделей."""
    result = await session.execute(
        select(Provider).where(Provider.is_active == True, Provider.type == "llm")
    )
    providers = result.scalars().all()

    models = []
    for provider in providers:
        models.append(
            {
                "id": f"{provider.name}/auto",
                "provider": provider.name,
                "type": "llm",
                "status": "available",
            }
        )
    return models
