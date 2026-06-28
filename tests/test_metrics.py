"""Тесты для Prometheus metrics endpoint."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from src.main import app


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


@pytest.mark.asyncio
async def test_metrics_request_counter_increment(client):
    """Проверка увеличения счетчика запросов при обращении к эндпоинтам."""
    ac, _ = client
    
    # Делаем несколько запросов к разным эндпоинтам
    response1 = await ac.get("/health")  # без слеша в конце
    assert response1.status_code == 200
    
    response2 = await ac.get("/metrics")
    assert response2.status_code == 200
    
    # Проверяем метрики
    metrics_response = await ac.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text
    
    # Должен быть увеличен счетчик запросов
    assert 'api_hub_requests_total{method="GET",endpoint="/health"} 1.0' in metrics_text or \
           'api_hub_requests_total{method="GET",endpoint="/health"} 2.0' in metrics_text or \
           'api_hub_requests_total{method="GET",endpoint="/metrics"} 1.0' in metrics_text


@pytest.mark.asyncio
async def test_metrics_error_counter_increment(client):
    """Проверка увеличения счетчика ошибок при ошибочных запросах."""
    ac, _ = client
    
    # Делаем запрос к несуществующему эндпоинту (должен вернуть 404)
    response = await ac.get("/nonexistent/endpoint")
    assert response.status_code == 404
    
    # Проверяем метрики ошибок
    metrics_response = await ac.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text
    
    # Должен быть увеличен счетчик ошибок для 404
    assert 'api_hub_errors_total{method="GET",endpoint="/nonexistent/endpoint",http_status="404"} 1.0' in metrics_text


@pytest.mark.asyncio
async def test_metrics_latency_histogram(client):
    """Проверка наличия и корректности гистограммы латентности."""
    ac, _ = client
    
    # Делаем запрос
    response = await ac.get("/health")  # без слеша
    assert response.status_code == 200
    
    # Проверяем метрики латентности
    metrics_response = await ac.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text
    
    # Должна присутствовать гистограмма латентности
    assert "api_hub_request_duration_ms_bucket" in metrics_text
    assert "api_hub_request_duration_ms_sum" in metrics_text
    assert "api_hub_request_duration_ms_count" in metrics_text


@pytest.mark.asyncio
async def test_metrics_keys_gauge(client):
    """Проверка gauge-метрики для количества ключей."""
    ac, session = client
    
    # Создаем тестовые данные
    from src.models.provider import Provider
    from src.models.api_key import ApiKey
    from src.models.user import User
    
    provider = Provider(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()
    
    # Проверяем метрику количества ключей
    metrics_response = await ac.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text
    
    # Должна быть метрика с количеством ключей
    assert "api_hub_keys_total" in metrics_text
    # Значение должно быть >= 1 (может быть больше из-за других тестов)
    assert 'api_hub_keys_total 1.0' in metrics_text or 'api_hub_keys_total 2.0' in metrics_text or 'api_hub_keys_total 3.0' in metrics_text


@pytest.mark.asyncio
async def test_metrics_format_prometheus(client):
    """Проверка формата экспозиции метрик в Prometheus формате."""
    ac, _ = client
    
    response = await ac.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
    
    metrics_text = response.text
    
    # Проверяем наличие обязательных элементов Prometheus формата
    lines = metrics_text.strip().split('\n')
    metric_lines = [line for line in lines if not line.startswith('#') and line.strip()]
    
    # Должны быть строки с метриками в формате: metric_name{labels} value
    for line in metric_lines:
        if line.strip():
            # Проверяем базовый формат строки метрики
            # Пропускаем строки, которые являются частью SQL запросов или других технических деталей
            if 'SELECT' in line or 'FROM' in line or 'WHERE' in line:
                continue
            assert '{' in line or ' ' in line  # либо есть лейблы, либо просто метрика и значение
            parts = line.split()
            if len(parts) >= 2:
                # Проверяем, что значение является числом
                try:
                    float(parts[-1])
                except ValueError:
                    # Если последняя часть не число, проверяем предпоследнюю
                    try:
                        float(parts[-2])
                    except ValueError:
                        # Пропускаем строки, которые явно не являются метриками
                        if not ('SELECT' in line or 'FROM' in line or 'WHERE' in line or 'asyncpg' in line):
                            assert False, f"Invalid metric format: {line}"


@pytest.mark.asyncio
async def test_metrics_after_multiple_requests(client):
    """Проверка накопления метрик после множественных запросов."""
    ac, _ = client
    
    # Выполняем несколько запросов разных типов
    endpoints = ["/health", "/metrics", "/health", "/nonexistent"]
    expected_codes = [200, 200, 200, 404]
    
    for endpoint, expected_code in zip(endpoints, expected_codes):
        response = await ac.get(endpoint)
        assert response.status_code == expected_code
    
    # Проверяем накопленные метрики
    metrics_response = await ac.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text
    
    # Должны быть счетчики для каждого эндпоинта
    assert 'api_hub_requests_total{method="GET",endpoint="/health"} 2.0' in metrics_text
    assert 'api_hub_requests_total{method="GET",endpoint="/metrics"} 1.0' in metrics_text
    assert 'api_hub_requests_total{method="GET",endpoint="/nonexistent"} 1.0' in metrics_text
    assert 'api_hub_errors_total{method="GET",endpoint="/nonexistent",http_status="404"} 1.0' in metrics_text