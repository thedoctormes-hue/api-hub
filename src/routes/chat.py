from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
import httpx
import time

from src.config.database import get_session
from src.models.user import User
from src.models.api_key import ApiKey
from src.models.provider import Provider
from src.models.request_log import RequestLog
from src.config.settings import get_settings

router = APIRouter()


@router.post("/chat/completions")
async def chat_completions(
    request: dict,
    session: AsyncSession = Depends(get_session),
):
    """Единый эндпоинт для chat completions (OpenAI-совместимый)."""
    start_time = time.time()
    settings = get_settings()

    # Находим пользователя (упрощённо: первого активного)
    user_result = await session.execute(select(User).where(User.is_active == True))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No active users found",
        )

    # Находим активные ключи для LLM-провайдеров
    keys_result = await session.execute(
        select(ApiKey, Provider)
        .join(Provider, ApiKey.provider_id == Provider.id)
        .where(
            ApiKey.user_id == user.id,
            ApiKey.is_active == True,
            Provider.is_active == True,
            Provider.type == "llm",
        )
        .order_by(Provider.rate_limit.desc())
    )
    key_provider_pairs = keys_result.all()
    if not key_provider_pairs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active LLM API keys found",
        )

    api_key, provider = key_provider_pairs[0]

    # Формируем заголовки
    headers = {"Content-Type": "application/json"}
    params = {}
    if provider.auth_type == "bearer":
        headers[provider.auth_key_name] = f"Bearer {api_key.key_ref}"
    elif provider.auth_type == "header":
        headers[provider.auth_key_name] = api_key.key_ref
    elif provider.auth_type == "query_param":
        params[provider.auth_key_name] = api_key.key_ref

    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    payload = request.copy()

    async with httpx.AsyncClient(timeout=provider.timeout_sec) as client:
        try:
            response = await client.request(
                method="POST",
                url=url,
                headers=headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPStatusError as e:
            error_detail = f"Provider error: {e.response.status_code}"
            try:
                error_detail += f" - {e.response.json()}"
            except Exception:
                error_detail += f" - {e.response.text}"

            log_entry = RequestLog(
                user_id=user.id,
                provider_id=provider.id,
                api_key_id=api_key.id,
                endpoint="/v1/chat/completions",
                method="POST",
                status_code=e.response.status_code,
                latency_ms=int((time.time() - start_time) * 1000),
                error=error_detail,
            )
            session.add(log_entry)
            await session.execute(
                update(ApiKey)
                .where(ApiKey.id == api_key.id)
                .values(last_status="error", last_used_at=func.now())
            )
            await session.commit()

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_detail,
            )
        except Exception as e:
            error_detail = f"Request failed: {str(e)}"
            log_entry = RequestLog(
                user_id=user.id,
                provider_id=provider.id,
                api_key_id=api_key.id,
                endpoint="/v1/chat/completions",
                method="POST",
                status_code=500,
                latency_ms=int((time.time() - start_time) * 1000),
                error=error_detail,
            )
            session.add(log_entry)
            await session.execute(
                update(ApiKey)
                .where(ApiKey.id == api_key.id)
                .values(last_status="error", last_used_at=func.now())
            )
            await session.commit()

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_detail,
            )

    latency_ms = int((time.time() - start_time) * 1000)

    if isinstance(result, dict):
        result.setdefault("_meta", {})
        result["_meta"].update(
            {
                "provider": provider.name,
                "latency_ms": latency_ms,
                "fallback_used": False,
            }
        )

        usage = result.get("usage", {})
        log_entry = RequestLog(
            user_id=user.id,
            provider_id=provider.id,
            api_key_id=api_key.id,
            endpoint="/v1/chat/completions",
            method="POST",
            status_code=response.status_code,
            latency_ms=latency_ms,
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
        )
        session.add(log_entry)
        await session.execute(
            update(ApiKey)
            .where(ApiKey.id == api_key.id)
            .values(last_status="ok", last_used_at=func.now())
        )

    await session.commit()
    return result
