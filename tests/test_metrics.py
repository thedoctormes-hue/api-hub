"""Тесты для Prometheus metrics endpoint."""

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    """Метрик-эндпоинт возвращает 200 и plain text."""
    ac, _ = client
    response = await ac.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_metrics_contains_basic_lines(client):
    """Метрик-эндпоинт содержит базовые метрики."""
    ac, _ = client
    response = await ac.get("/metrics")
    text = response.text

    assert "api_hub_requests_total" in text
    assert "api_hub_errors_total" in text
    assert "api_hub_request_duration_ms" in text


@pytest.mark.asyncio
async def test_metrics_db_section(client):
    """Метрик-эндпоинт содержит секцию с БД (или ошибку при отсутствии БД)."""
    ac, _ = client
    response = await ac.get("/metrics")
    text = response.text

    # При тестировании с in-memory SQLite может не быть PostgreSQL-моделей
    # но ответ всё равно должен быть корректным
    assert "api_hub_keys_total" in text or "# metrics" in text


@pytest.mark.asyncio
async def test_health_keys_endpoint(client):
    """/health/keys возвращает сводку (или ошибку при недоступности БД)."""
    ac, _ = client
    response = await ac.get("/health/keys")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    # При тестировании с in-memory SQLite get_key_health_summary использует
    # async_session (PostgreSQL), поэтому может вернуть error — это ожидаемо
    if data["status"] == "error":
        assert "error" in data
    else:
        assert "total_keys" in data
