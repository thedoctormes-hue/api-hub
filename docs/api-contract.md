# 📡 API-контракт

**Версия:** 0.1 | **Дата:** 2026-06-19

---

## Авторизация

Все запросы к API Hub требуют заголовка:
```
Authorization: Bearer <api_key>
```

API-ключ выдаётся при регистрации агента.

---

## Управление ключами

### Загрузить ключ
```
POST /keys
Content-Type: application/json

{
  "provider": "openrouter",
  "api_key": "sk-or-v1-xxxxxxxxxxxxxxxx",
  "alias": "основной"
}

Response 201:
{
  "id": "uuid",
  "provider": "openrouter",
  "alias": "основной",
  "status": "ok",
  "created_at": "2026-06-19T14:00:00Z"
}
```

### Список ключей
```
GET /keys

Response 200:
{
  "keys": [
    {
      "id": "uuid",
      "provider": "openrouter",
      "alias": "основной",
      "status": "ok",
      "last_used_at": "2026-06-19T14:00:00Z"
    }
  ]
}
```

### Удалить ключ
```
DELETE /keys/{id}

Response 204
```

### Проверить ключ
```
GET /keys/{id}/status

Response 200:
{
  "id": "uuid",
  "provider": "openrouter",
  "status": "ok",
  "rate_limit_remaining": 100,
  "checked_at": "2026-06-19T14:00:00Z"
}
```

---

## LLM запросы

### Chat Completions (OpenAI-совместимый)
```
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "openrouter/auto",
  "messages": [
    {"role": "user", "content": "Привет!"}
  ],
  "max_tokens": 1000,
  "temperature": 0.7
}

Response 200:
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1718800000,
  "model": "openrouter/auto",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Привет! Как дела?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  },
  "_meta": {
    "provider": "openrouter",
    "latency_ms": 500,
    "fallback_used": false
  }
}
```

### Список доступных моделей
```
GET /v1/models

Response 200:
{
  "models": [
    {
      "id": "openrouter/auto",
      "provider": "openrouter",
      "type": "llm",
      "status": "available"
    },
    {
      "id": "gpt-4o",
      "provider": "openai",
      "type": "llm",
      "status": "available"
    }
  ]
}
```

---

## Геокодирование

### Геокод адреса
```
POST /v1/geocode
Content-Type: application/json

{
  "query": "Москва, Красная площадь, 1"
}

Response 200:
{
  "results": [
    {
      "address": "г Москва, пл Красная, д 1",
      "lat": 55.7535,
      "lon": 37.6212,
      "federal_district": "Центральный",
      "region": "Москва"
    }
  ],
  "_meta": {
    "provider": "dadata",
    "latency_ms": 120
  }
}
```

---

## Валидация

### Валидация email
```
POST /v1/validate/email
Content-Type: application/json

{
  "value": "test@example.com"
}

Response 200:
{
  "valid": true,
  "is_disposable": false,
  "is_free": true,
  "_meta": {
    "provider": "abstractapi",
    "latency_ms": 80
  }
}
```

### Валидация телефона
```
POST /v1/validate/phone
Content-Type: application/json

{
  "value": "+79991234567"
}

Response 200:
{
  "valid": true,
  "country": "RU",
  "carrier": "MTS",
  "type": "mobile",
  "_meta": {
    "provider": "abstractapi",
    "latency_ms": 90
  }
}
```

---

## Скрапинг

### Скрапинг URL
```
POST /v1/scrape
Content-Type: application/json

{
  "url": "https://example.com",
  "render_js": false
}

Response 200:
{
  "status": "ok",
  "content": "<html>...</html>",
  "content_type": "text/html",
  "_meta": {
    "provider": "scraperapi",
    "latency_ms": 2000
  }
}
```

---

## Генерация PDF

### Генерация PDF из HTML
```
POST /v1/generate/pdf
Content-Type: application/json

{
  "html": "<h1>Отчёт</h1><p>Текст отчёта</p>",
  "filename": "report.pdf",
  "format": "A4"
}

Response 200:
{
  "url": "https://storage.example.com/reports/report.pdf",
  "expires_at": "2026-06-20T14:00:00Z",
  "_meta": {
    "provider": "pdfgeneratorapi",
    "latency_ms": 1500
  }
}
```

---

## Квоты

### Получить текущие квоты
```
GET /quotas

Response 200:
{
  "quotas": [
    {
      "provider": "openrouter",
      "period": "day",
      "limit": 1000,
      "used": 234,
      "remaining": 766,
      "reset_at": "2026-06-20T00:00:00Z"
    }
  ]
}
```

---

## Метрики

### Метрики использования
```
GET /metrics?period=day

Response 200:
{
  "period": "day",
  "total_requests": 1523,
  "total_tokens_in": 450000,
  "total_tokens_out": 120000,
  "avg_latency_ms": 350,
  "error_rate": 0.02,
  "by_provider": [
    {
      "provider": "openrouter",
      "requests": 1200,
      "tokens_in": 350000,
      "avg_latency_ms": 300
    },
    {
      "provider": "openai",
      "requests": 323,
      "tokens_in": 100000,
      "avg_latency_ms": 500
    }
  ]
}
```

---

## Ошибки

Все ошибки возвращаются в едином формате:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded for provider openrouter",
    "details": {
      "provider": "openrouter",
      "retry_after": 60
    }
  }
}
```

### Коды ошибок

| Код | HTTP | Описание |
|---|---|---|
| `unauthorized` | 401 | Невалидный API-ключ |
| `forbidden` | 403 | Нет доступа к провайдеру |
| `not_found` | 404 | Ключ или провайдер не найден |
| `rate_limit_exceeded` | 429 | Превышен rate limit |
| `provider_error` | 502 | Ошибка провайдера |
| `all_providers_failed` | 503 | Все провайдеры недоступны |
| `quota_exceeded` | 429 | Превышена квота |
| `validation_error` | 400 | Ошибка валидации запроса |
