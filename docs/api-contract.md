# 📡 API-контракт

**Версия:** 0.2 | **Дата:** 2026-06-28

---

## Авторизация

Все запросы к API Hub используют master-ключ для управления ключами и проксирование запросов к провайдерам через загруженные API-ключи.

```
Authorization: Bearer <master_key>
```

---

## Health & Monitoring

### Базовый health-check
```
GET /health

Response 200:
{
  "status": "ok",
  "service": "API Hub",
  "version": "0.2.0",
  "database": "ok"
}
```

### Детальный health-check ключей
```
GET /health/keys

Response 200:
{
  "status": "healthy | degraded | critical | no_keys",
  "total_keys": 10,
  "healthy_keys": 8,
  "key_statuses": {"ok": 8, "error": 2},
  "circuit_breakers": {"closed": 9, "open": 1},
  "recent_errors_5m": 3
}
```

### Prometheus метрики
```
GET /metrics

Response 200 (text/plain; version=0.0.4):
# HELP api_hub_requests_total Total number of requests
# TYPE api_hub_requests_total counter
api_hub_requests_total 1523
...
```

---

## Управление ключами

### Загрузить ключ
```
POST /keys/?provider_name=openrouter&api_key=sk-or-v1-xxx&alias=основной

Response 201:
{
  "id": "uuid",
  "provider": "openrouter",
  "alias": "основной",
  "status": "ok",
  "created_at": "2026-06-28T14:00:00Z"
}
```

При повторной загрузке с тем же alias — обновляется существующий ключ (upsert).

### Список ключей
```
GET /keys/

Response 200:
[
  {
    "id": "uuid",
    "user": "default_user",
    "provider": "openrouter",
    "alias": "основной",
    "status": "ok",
    "last_used_at": "2026-06-28T14:00:00Z",
    "created_at": "2026-06-28T13:00:00Z"
  }
]
```

### Удалить ключ
```
DELETE /keys/{id}

Response 204
```

Soft delete — ключ помечается `is_active=False` и исключается из ротации.

### Проверить статус ключа
```
GET /keys/{id}/status

Response 200:
{
  "id": "uuid",
  "provider": "openrouter",
  "status": "ok",
  "rate_limit_remaining": null,
  "checked_at": "2026-06-28T14:00:00Z"
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
[
  {
    "id": "openrouter/auto",
    "provider": "openrouter",
    "type": "llm",
    "status": "available"
  }
]
```

---

## Ошибки

Все ошибки возвращаются в стандартном FastAPI формате:

```json
{
  "detail": "Описание ошибки"
}
```

### Коды ответов

| Код | Описание |
|---|---|
| 200 | Успех |
| 201 | Создано (ключ загружен) |
| 204 | Удалено (ключ деактивирован) |
| 400 | Нет активных LLM-ключей или невалидный запрос |
| 404 | Ключ или провайдер не найден |
| 502 | Ошибка провайдера (HTTPStatusError или таймаут) |
