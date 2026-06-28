# 📊 Мониторинг и Observability

**Версия:** 0.2 | **Дата:** 2026-06-28

---

## Обзор

API Hub предоставляет три уровня наблюдаемости:

1. **Health Endpoints** — быстрая проверка состояния
2. **Prometheus Metrics** — метрики для сбора и алертинга
3. **Request Logging** — детальные логи каждого запроса в БД

---

## Health Endpoints

### GET /health

Базовый health check. Проверяет доступность БД.

```json
{
  "status": "ok",
  "service": "API Hub",
  "version": "0.2.0",
  "database": "ok"
}
```

Используется для:
- Docker healthcheck
- Kubernetes liveness probe
- Load balancer health check

### GET /health/keys

Детальный health-check всех ключей с circuit breaker статусами.

```json
{
  "status": "healthy",
  "total_keys": 27,
  "healthy_keys": 25,
  "key_statuses": {
    "ok": 25,
    "error": 1,
    "circuit_open": 1
  },
  "circuit_breakers": {
    "closed": 26,
    "open": 1
  },
  "recent_errors_5m": 2
}
```

**Overall status logic:**
- `no_keys` — нет активных ключей
- `healthy` — все ключи ok
- `degraded` — часть ключей в ошибке
- `critical` — нет ни одного рабочего ключа
- `error` — ошибка при проверке

Используется для:
- Kubernetes readiness probe
- Мониторинг деградации
- Автоматическое оповещение

---

## Prometheus Metrics

### GET /metrics

Эндпоинт в формате [Prometheus text exposition](https://prometheus.io/docs/instrumenting/exposition_formats/).

### Request Metrics

**api_hub_requests_total** (counter)
- Общее количество запросов
- Обновляется из middleware

**api_hub_errors_total** (counter)
- Количество запросов с status >= 400
- Позволяет считать error rate

**api_hub_request_duration_ms** (histogram)
- Распределение латентности
- Buckets: 10, 50, 100, 250, 500, 1000, 5000, 10000 ms
- Позволяет считать P50/P95/P99

### Key Health Metrics

**api_hub_keys_total** (gauge, label: status)
- Количество ключей по последнему статусу
- Статусы: ok, error, timeout, circuit_open, unknown

**api_hub_active_keys** (gauge)
- Общее количество активных ключей

**api_hub_circuit_breakers** (gauge, label: state)
- Количество circuit breaker по состояниям
- Состояния: closed, open, half-open

### Health Check Metrics

**api_hub_health_checks_5m** (gauge, label: status)
- Результаты health-check за последние 5 минут
- Статусы: ok, error, timeout, rate_limited

**api_hub_avg_health_latency_ms** (gauge)
- Средняя латентность health-check (5 мин)

### Request Log Metrics

**api_hub_requests_5m** (gauge)
- Количество запросов за последние 5 минут

**api_hub_avg_request_latency_ms** (gauge)
- Средняя латентность запросов (5 мин)

---

## Prometheus Configuration

### prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'api-hub'
    static_configs:
      - targets: ['api-hub:8000']
    metrics_path: /metrics
    scrape_interval: 15s
```

### Docker Compose

```bash
# Запуск с мониторингом
docker-compose --profile monitoring up -d

# Prometheus доступен на http://localhost:9090
```

---

## Circuit Breaker

### Логика работы

Circuit breaker защищает систему от неработающих ключей:

```
[cLOSED] --3 errors--> [OPEN] --5 min cooldown--> [HALF-OPEN] --success--> [CLOSED]
                                                          --error--> [OPEN]
```

**Параметры:**
- `FAIL_THRESHOLD = 3` — количество ошибок до открытия
- `COOLDOWN_SECONDS = 300` — время cooldown (5 минут)

**Состояния:**
- **closed** — ключ работает, запросы проходят
- **open** — ключ отключен, запросы не отправляются
- **half-open** — пробный запрос для проверки восстановления

### Модель данных

```sql
CREATE TABLE circuit_breakers (
    id UUID PRIMARY KEY,
    provider_id UUID REFERENCES providers(id),
    api_key_id UUID REFERENCES api_keys(id),
    state VARCHAR(16) DEFAULT 'closed',
    fail_count INTEGER DEFAULT 0,
    last_failure TIMESTAMPTZ,
    last_success TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    half_open_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

### Health-Check алгоритм

1. Для каждого активного ключа проверяем circuit breaker state
2. Если `open` и cooldown не истёк — пропускаем (circuit_open)
3. Если `open` и cooldown истёк — переводим в `half-open`, делаем пробный запрос
4. Если `closed` или `half-open` — выполняем health-check запрос
5. При успехе → `closed`, fail_count = 0
6. При ошибке → fail_count++, при >= 3 → `open`

### Интервалы health-check

| Тип провайдера | Интервал |
|---|---|
| llm | 30 сек |
| image | 120 сек |
| agent | 120 сек |
| scrape | 120 сек |
| generate | 120 сек |
| geocode | 300 сек |
| validate | 300 сек |
| search | 300 сек |
| ocr | 600 сек |
| tts | 600 сек |

---

## Алерты

### Рекомендации

**Critical:**
- `api_hub_active_keys < 5` — критически мало активных ключей
- `api_hub_circuit_breakers{state="open"} > 5` — много отключенных ключей

**Warning:**
- `api_hub_errors_total` rate > 10 за 5 минут
- `api_hub_circuit_breakers{state="open"} > 2`
- `api_hub_avg_request_latency_ms > 5000` — высокая латентность

**Info:**
- `api_hub_requests_5m == 0` более 30 минут — нет трафика
- `api_hub_health_checks_5m{status="error"} > 3` — рост ошибок health-check

### Prometheus Alert Rules

```yaml
groups:
  - name: api-hub
    rules:
      - alert: APIHubHighErrorRate
        expr: rate(api_hub_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on API Hub"

      - alert: APIHubCircuitBreakerOpen
        expr: api_hub_circuit_breakers{state="open"} > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Multiple circuit breakers open"

      - alert: APIHubLowActiveKeys
        expr: api_hub_active_keys < 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Low number of active API keys"
```

---

## Логирование

### Request Log

Каждый запрос логируется в таблицу `request_log`:
- user_id, provider_id, api_key_id
- endpoint, method, status_code
- latency_ms, tokens_in, tokens_out
- error (если есть)
- created_at

### Key Health Log

Результаты health-check логируются в `key_health_log`:
- api_key_id, status, latency_ms
- error_text (если есть)
- checked_at

### Уровни логирования

Настраивается через `LOG_LEVEL`:
- `DEBUG` — детальные логи health-check
- `INFO` — циклы health-check, circuit breaker transitions
- `WARNING` — ошибки ключей, connection errors
- `ERROR` — непредвиденные ошибки
