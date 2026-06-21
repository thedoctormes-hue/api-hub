"""Базовое middleware для rate limiting (упрощённо для MVP)."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
import time
from typing import Callable
from src.config.settings import get_settings

# В проде: использовать Redis для хранения счётчиков
# Для MVP: словарь в памяти (не подходит для множества воркеров, но ok для single-process dev)
_request_counts = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls_per_minute: int = 60):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Для MVP: не делаем ничего сложного, просто пропускаем
        # TODO: реализовать proper rate limiting через Redis
        return await call_next(request)
