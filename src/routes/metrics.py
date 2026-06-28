"""Prometheus metrics endpoint.

Exposes /metrics in Prometheus text format with:
- Request count by endpoint/status/method
- Request latency histogram
- Error count by status code
- API key health status
- Circuit breaker state
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from src.config.database import async_session
from src.models.api_key import ApiKey
from src.models.circuit_breaker import CircuitBreaker
from src.models.key_health_log import KeyHealthLog
from src.models.request_log import RequestLog

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory counters (sufficient for single-process behind Prometheus scrape)
# For multi-process deployments, use prometheus-client multiprocess mode
_metrics = {
    "requests_total": 0,
    "errors_total": 0,
    "request_duration_ms_total": 0.0,
    "duration_buckets": {10: 0, 50: 0, 100: 0, 250: 0, 500: 0, 1000: 0, 5000: 0, 10000: 0},
}


def record_request(method: str, endpoint: str, status_code: int, latency_ms: float):
    """Record a request for metrics. Called from middleware."""
    _metrics["requests_total"] += 1
    _metrics["request_duration_ms_total"] += latency_ms

    if status_code >= 400:
        _metrics["errors_total"] += 1

    # Histogram buckets
    for bucket in sorted(_metrics["duration_buckets"].keys()):
        if latency_ms <= bucket:
            _metrics["duration_buckets"][bucket] += 1
            break


@router.get("/metrics")
async def metrics():
    """Prometheus exposition format."""
    lines = []
    now = int(time.time() * 1000)

    # Request count
    lines.append("# HELP api_hub_requests_total Total number of requests")
    lines.append("# TYPE api_hub_requests_total counter")
    lines.append(f'api_hub_requests_total { _metrics["requests_total"] } {now}')

    # Error count
    lines.append("# HELP api_hub_errors_total Total number of errors (status >= 400)")
    lines.append("# TYPE api_hub_errors_total counter")
    lines.append(f'api_hub_errors_total { _metrics["errors_total"] } {now}')

    # Latency histogram
    lines.append("# HELP api_hub_request_duration_ms Request latency distribution")
    lines.append("# TYPE api_hub_request_duration_ms histogram")
    cumulative = 0
    for bucket in sorted(_metrics["duration_buckets"].keys()):
        cumulative += _metrics["duration_buckets"][bucket]
        lines.append(f'api_hub_request_duration_ms_bucket{{le="{bucket}"}} {cumulative}')
    lines.append(f'api_hub_request_duration_ms_bucket{{le="+Inf"}} {_metrics["requests_total"]}')
    lines.append(f'api_hub_request_duration_ms_sum {_metrics["request_duration_ms_total"]}')
    lines.append(f'api_hub_request_duration_ms_count {_metrics["requests_total"]}')

    # Database metrics: key health
    try:
        async with async_session() as session:
            # Total keys by status
            result = await session.execute(
                select(
                    ApiKey.last_status,
                    func.count(ApiKey.id),
                ).group_by(ApiKey.last_status)
            )
            lines.append("# HELP api_hub_keys_total Total API keys by last status")
            lines.append("# TYPE api_hub_keys_total gauge")
            for status, count in result.all():
                status_label = status or "unknown"
                lines.append(f'api_hub_keys_total{{status="{status_label}"}} {count}')

            # Active keys count
            result = await session.execute(
                select(func.count(ApiKey.id)).where(ApiKey.is_active)
            )
            active_count = result.scalar_one()
            lines.append("# HELP api_hub_active_keys Active API keys count")
            lines.append("# TYPE api_hub_active_keys gauge")
            lines.append(f"api_hub_active_keys {active_count}")

            # Circuit breaker states
            result = await session.execute(
                select(
                    CircuitBreaker.state,
                    func.count(CircuitBreaker.id),
                ).group_by(CircuitBreaker.state)
            )
            lines.append("# HELP api_hub_circuit_breakers Circuit breaker states")
            lines.append("# TYPE api_hub_circuit_breakers gauge")
            for state, count in result.all():
                lines.append(f'api_hub_circuit_breakers{{state="{state}"}} {count}')

            # Recent health check results (last 5 min)
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
            result = await session.execute(
                select(
                    KeyHealthLog.status,
                    func.count(KeyHealthLog.id),
                ).where(KeyHealthLog.checked_at >= cutoff).group_by(KeyHealthLog.status)
            )
            lines.append("# HELP api_hub_health_checks_5m Health check results in last 5 minutes")
            lines.append("# TYPE api_hub_health_checks_5m gauge")
            for status, count in result.all():
                lines.append(f'api_hub_health_checks_5m{{status="{status}"}} {count}')

            # Average latency from health checks (last 5 min)
            result = await session.execute(
                select(func.avg(KeyHealthLog.latency_ms)).where(
                    KeyHealthLog.checked_at >= cutoff,
                    KeyHealthLog.latency_ms.isnot(None),
                )
            )
            avg_latency = result.scalar_one_or_none()
            lines.append("# HELP api_hub_avg_health_latency_ms Average health check latency (last 5m)")
            lines.append("# TYPE api_hub_avg_health_latency_ms gauge")
            lines.append(f"api_hub_avg_health_latency_ms {avg_latency or 0}")

            # Request log stats (last 5 min)
            result = await session.execute(
                select(
                    func.count(RequestLog.id),
                    func.avg(RequestLog.latency_ms),
                ).where(RequestLog.created_at >= cutoff)
            )
            total_req, avg_req_latency = result.one()
            lines.append("# HELP api_hub_requests_5m Total requests in last 5 minutes")
            lines.append("# TYPE api_hub_requests_5m gauge")
            lines.append(f"api_hub_requests_5m {total_req or 0}")

            lines.append("# HELP api_hub_avg_request_latency_ms Average request latency (last 5m)")
            lines.append("# TYPE api_hub_avg_request_latency_ms gauge")
            lines.append(f"api_hub_avg_request_latency_ms {avg_req_latency or 0}")

    except Exception as e:
        logger.error(f"Failed to collect DB metrics: {e}")
        lines.append(f'# metrics collection error: {e}')

    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4",
    )
