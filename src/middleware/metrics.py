"""Middleware for collecting Prometheus metrics on every request."""

import logging
import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.routes.metrics import record_request

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records request count, latency, and errors for Prometheus."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics scraping itself
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        latency_ms = (time.monotonic() - start) * 1000

        record_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        return response
