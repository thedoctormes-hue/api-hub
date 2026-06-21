# 🔌 API Hub

> **Владелец:** DoctorM&Ai | **Статус:** active | **Версия:** 0.1.0

## Описание

Универсальный API-шлюз для всех внешних API. Загружаешь свои ключи — получаешь один эндпoinт с маршрутизацией, мониторингом, fallback и rate limiting. В отличие от OpenRouter и LiteLLM, работает не только с LLM, а с любыми API.

---

## Концепт

Пользователь загружает свои API-ключи от разных провайдеров (LLM, гео, скрапинг, генерация — любые). Сервис предоставляет **единый API-эндпоинт** с маршрутизацией, мониторингом, fallback и rate limiting.

**Ключевая идея:** все существующие решения (OpenRouter, LiteLLM) — только про LLM. Мы делаем **универсальный шлюз для любых API**.

---

## Быстрый старт

```bash
# Клонировать
git clone <repo> && cd projects/api-hub

# Запуск через Docker
docker-compose up -d

# Или локально
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

API доступен на `http://localhost:8000`

---

## API

### Health Check
```
GET /health
```
```json
{
  "status": "ok",
  "service": "API Hub",
  "version": "0.1.0",
  "database": "ok"
}
```

### Управление ключами
```
POST   /keys/          — загрузить ключ
GET    /keys/          — список ключей
DELETE /keys/{id}      — удалить ключ (soft delete)
GET    /keys/{id}/status — проверить работоспособность
```

### Chat Completions (OpenAI-совместимый)
```
POST /v1/chat/completions
```
Проксирует запрос к активному LLM-провайдеру. Добавляет `_meta` с информацией о провайдере и latency.

### Список моделей
```
GET /v1/models
```
Возвращает список доступных моделей от активных LLM-провайдеров.

---

## Архитектура

### Стек
- **FastAPI** — async web framework
- **SQLAlchemy 2.0 + asyncpg** — ORM и драйвер PostgreSQL
- **PostgreSQL** — хранение конфигов, ключей (refs), логов, квот
- **Redis** (планируется) — rate limiting, circuit breaker state
- **HashiCorp Vault** (планируется) — шифрование ключей

### Модель данных
```
User (1) → (N) ApiKey (N) → (1) Provider
User (1) → (N) Quota (N) → (1) Provider
ApiKey (1) → (N) RequestLog
ApiKey (1) → (1) CircuitBreaker
```

### Маршрутизация
- **L1** — выбор провайдера по типу запроса (llm, geocode, validate, scrape, generate)
- **L2** — приоритет по rate limit (проксируем на самый свободный)
- **L3** — circuit breaker на каждого провайдера

### Провайдеры (7 в MVP)
| Провайдер | Тип | Авторизация |
|---|---|---|
| openrouter | llm | Bearer |
| openai | llm | Bearer |
| anthropic | llm | Header (x-api-key) |
| dadata | geocode | Header (Authorization) |
| abstractapi | validate | Query param |
| scraperapi | scrape | Query param |
| pdfgeneratorapi | generate | Bearer |

---

## Разработка

```bash
# Запуск в dev-режиме
uvicorn src.main:app --reload --port 8000

# Линтер
ruff check src/

# Форматирование
ruff format src/
```

## Деплой

```bash
docker-compose up -d
```

Health check: `GET /health`

## Тестирование

```bash
# Запуск тестов
python3 -m pytest tests/ -v

# С coverage
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

Тесты используют SQLite in-memory с dependency override (без реального PostgreSQL).

---

## Конфигурация

Провайдеры сидируются автоматически при первом запуске (см. `src/config/database.py` → `DEFAULT_PROVIDERS`).

Дополнительные конфиги провайдеров: `config/providers/*.yaml`

---

## Roadmap

| Этап | Что |
|---|---|
| ✅ MVP | FastAPI прокси, 7 провайдеров, 6 моделей, тесты |
| v2 | lab-vault интеграция, circuit breaker, per-agent квоты |
| v2 | Fallback между провайдерами, не-LLM эндпоинты |
| v3 | Go gateway, Prometheus/Grafana, публичный продукт |

---

## Документация

- [Архитектура](docs/ARCHITECTURE.md)
- [API](docs/api/)
- [ADR](docs/adr/)

## Связь с проектами колонии

| Проект | Роль |
|---|---|
| **lab-vault** | Хранилище ключей (источник правды) |
| **myrmex-control** | Метрики, мониторинг, rate limits |
| **free-api-hunter** | Каталог бесплатных API как fallback |

---

## Аналоги на рынке

- **OpenRouter** — лидер, 200+ моделей, только LLM
- **LiteLLM** — open-source self-hosted, только LLM
- **Merge Gateway** — коммерческий шлюз с аналитикой
- **Zuplo** — edge-native gateway, бесплатный tier

**Наше отличие:** универсальный шлюз для любых API, не только LLM.
