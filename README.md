# 🔌 API Hub

> Единый API-шлюз для всех внешних API. Загружаешь свои ключи — получаешь один эндпоинт для всего.

**Статус:** v0.2 | **Версия:** 0.2.0 | **Обновлено:** 2026-06-28

---

## Концепт

Пользователь загружает свои API-ключи от разных провайдеров (LLM, гео, скрапинг, генерация — любые). Сервис предоставляет **единый API-эндпоинт** с маршрутизацией, мониторингом, fallback и rate limiting.

**Ключевая идея:** все существующие решения (OpenRouter, LiteLLM) — только про LLM. Мы делаем **универсальный шлюз для любых API**.

## Бесплатные ключи

Проект интегрирован с free-api-hunter. Предзагружены бесплатные ключи от 10+ провайдеров: Cerebras, Cohere, Mistral, Cloudflare Workers AI, ElevenLabs, Gemini, Manus, Pollinations, OCR.space, AbstractAPI.

Ключи автоматически проверяются health-check сервисом. Неработающие отключаются через circuit breaker (3 ошибки → cooldown 5 мин).

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

### Провайдеры (16 в v0.2)
| Провайдер | Тип | Авторизация | Бесплатный |
|---|---|---|---|
| openrouter | llm | Bearer | 20 req/min |
| openai | llm | Bearer | нет |
| anthropic | llm | Header | нет |
| cerebras | llm | Bearer | да |
| cloudflare | llm | Bearer | да |
| cohere | llm | Bearer | да |
| gemini | llm | Query param | да |
| mistral | llm | Bearer | да |
| dadata | geocode | Header | 10000/день |
| abstractapi | validate | Query param | 100/мес |
| scraperapi | scrape | Query param | 1000/мес |
| pdfgeneratorapi | generate | Bearer | 3/день |
| ocr-space | ocr | Header | да |
| elevenlabs | tts | Header | да |
| pollinations | image | none | да |
| manus | agent | Header | да |

---

## Тестирование

```bash
# Запуск всех тестов
python3 -m pytest tests/ -v

# С coverage
python3 -m pytest tests/ --cov=src --cov-report=term-missing

# Конкретный модуль
python3 -m pytest tests/test_health_check.py -v
```

74+ тестов покрывают: модели, роуты, health-check, circuit breaker, метрики.
Тесты используют SQLite in-memory с dependency override (без реального PostgreSQL).

---

## Конфигурация

Провайдеры сидируются автоматически при первом запуске (см. `src/config/database.py` → `DEFAULT_PROVIDERS`).

Дополнительные конфиги провайдеров: `config/providers/*.yaml`

---

## Deployment

### Docker (рекомендуемый)

```bash
# Сборка и запуск
docker-compose up -d --build

# Проверка статуса
docker-compose ps
docker-compose logs -f api-hub

# Остановка
docker-compose down
```

### Ручной запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Переменные окружения
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/apihub
export MASTER_KEY=your-secret-master-key

# Запуск
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/apihub` | URL базы данных |
| `MASTER_KEY` | `dev-master-key` | Мастер-ключ для управления |
| `APP_VERSION` | `0.2.0` | Версия сервиса |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

### Проверка работоспособности

```bash
# Health check
curl http://localhost:8000/health

# Метрики Prometheus
curl http://localhost:8000/metrics

# Список ключей
curl http://localhost:8000/keys/
```

---

## Roadmap

| Этап | Что |
|---|---|
| ✅ MVP | FastAPI прокси, 7 провайдеров, тесты |
| ✅ v0.2 | 16 провайдеров, circuit breaker, health-check, Prometheus метрики, 74+ тестов |
| v0.3 | lab-vault интеграция, per-agent квоты, API contract v2 |
| v1.0 | Fallback между провайдерами, не-LLM эндпоинты, rate limiting |
| v2.0 | Go gateway, Prometheus/Grafana, публичный продукт |

---

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
