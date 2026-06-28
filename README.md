# 🔌 API Hub

> Единый API-шлюз для всех внешних API. Загружаешь свои ключи — получаешь один эндпоинт для всего.

**Статус:** v0.2 | **Версия:** 0.2.0 | **Обновлено:** 2026-06-28

---

## Концепт

Пользователь загружает свои API-ключи от разных провайдеров (LLM, гео, скрапинг, генерация — любые). Сервис предоставляет **единый API-эндпоинт** с маршрутизацией, мониторингом, fallback и rate limiting.

**Ключевая идея:** все существующие решения (OpenRouter, LiteLLM) — только про LLM. Мы делаем **универсальный шлюз для любых API**.

## Бесплатные ключи

Проект интегрирован с free-api-hunter. Предзагружены **27 бесплатных ключей от 9 провайдеров**: Cerebras (6), Cohere (4), ElevenLabs (9), Mistral (2), Cloudflare Workers AI (1), Gemini (1), Manus (2), Pollinations (1), OCR.space (1).

Ключи автоматически проверяются health-check сервисом. Неработающие отключаются через circuit breaker (3 ошибки → cooldown 5 мин).

---

## Supported Providers

### LLM (Large Language Providers)

- **Cerebras** — GLM-4.7, 5 req/min, бесплатный через free-api-hunter
- **Cloudflare Workers AI** — Llama 3.3 70B, Llama 4 Scout, GPT-oss 120B; 10000 req/день
- **Cohere** — бесплатный tier, tokens/month limit
- **Gemini** — Google Gemini API, бесплатный tier
- **Mistral** — бесплатный tier, tokens/minute limit
- **OpenRouter** — 200+ моделей, 20 req/min бесплатный tier
- **OpenAI** — платный, Bearer auth
- **Anthropic** — Claude Sonnet 4, платный, Header auth

### Media & Generation

- **ElevenLabs** — TTS, бесплатный tier, characters/month limit
- **Pollinations** — генерация изображений, без авторизации, бесплатный

### Data & Scraping

- **OCR.space** — OCR, бесплатный tier
- **DaData** — геокодирование, 10000 req/день
- **AbstractAPI** — валидация email, 100 req/месяц
- **ScraperAPI** — веб-скрапинг, 1000 req/месяц
- **PDFGeneratorAPI** — генерация PDF, 3 req/день

### Agent

- **Manus** — AI-агент, бесплатный tier через free-api-hunter

### Provider Configuration

Каждый провайдер описывается YAML-конфигурацией в `config/providers/<name>.yaml`. Конфиг определяет: base_url, тип авторизации (bearer/header/query_param), rate limits, timeout, retry policy, health-check endpoint.

База данных при первом запуске сидирует 7 провайдеров (openrouter, openai, anthropic, dadata, abstractapi, scraperapi, pdfgeneratorapi). Остальные провайдеры добавляются через YAML-конфиги или API.

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

### Импорт бесплатных ключей

```bash
# Экспорт ключей из free-api-hunter vault
python3 scripts/export_free_keys.py > free_keys.json

# Импорт в api-hub
python3 scripts/import_free_keys.py free_keys.json
```

---

## API

### Health Check
```
GET /health          — базовый health check
GET /health/keys     — детальный статус всех ключей и circuit breaker
```

`/health` ответ:
```json
{
  "status": "ok",
  "service": "API Hub",
  "version": "0.2.0",
  "database": "ok"
}
```

`/health/keys` ответ:
```json
{
  "status": "healthy",
  "total_keys": 27,
  "healthy_keys": 25,
  "key_statuses": {"ok": 25, "error": 1, "circuit_open": 1},
  "circuit_breakers": {"closed": 26, "open": 1},
  "recent_errors_5m": 2
}
```

### Key Management
```
POST   /keys/          — загрузить ключ (provider_name, api_key, alias)
GET    /keys/          — список всех активных ключей (без значений)
DELETE /keys/{id}      — удалить ключ (soft delete)
GET    /keys/{id}/status — проверить работоспособность ключа
```

Ключи хранятся как SHA-256 хеши (`key_ref`). Значения разрешаются через vault backup при health-check.

Пример добавления ключа:
```bash
curl -X POST http://localhost:8000/keys/ \
  -H "Content-Type: application/json" \
  -d '{"provider_name": "cerebras", "api_key": "csk-...", "alias": "cerebras-1"}'
```

### Chat Completions (OpenAI-совместимый)
```
POST /v1/chat/completions
```
Проксирует запрос к активному LLM-провайдеру с наивысшим rate limit. Добавляет `_meta` с информацией о провайдере и latency. Логирует запрос в `request_log`.

### Список моделей
```
GET /v1/models
```
Возвращает список доступных моделей от активных LLM-провайдеров.

### Prometheus Metrics
```
GET /metrics
```
Эндпоинт в формате Prometheus text exposition. Подробнее — [docs/monitoring.md](docs/monitoring.md).

---

## Key Management

### Добавление ключей

Ключи добавляются через API или скриптом импорта:

```bash
# Через API
curl -X POST http://localhost:8000/keys/ \
  -d '{"provider_name": "cerebras", "api_key": "csk-...", "alias": "my-key"}'

# Массовый импорт из free-api-hunter
python3 scripts/export_free_keys.py > free_keys.json
python3 scripts/import_free_keys.py free_keys.json
```

### Хранение ключей

Ключи хранятся в БД как SHA-256 хеши (`key_ref`). Фактические значения разрешаются через vault backup (`/root/LabDoctorM/vault/free-api-hunter/secrets-backup.json`) при health-check. Это позволяет не хранить открытые ключи в БД api-hub.

### Health-Check

Health-check проверяет каждый активный ключ через `/models` (LLM) или `/health` (остальные) эндпоинт провайдера. Интервалы проверки зависят от типа провайдера:

- LLM: 30 сек
- Image/Agent/Scrape/Generate: 120 сек
- Geocode/Validate/Search: 300 сек
- OCR/TTS: 600 сек

### Circuit Breaker

Механизм circuit breaker защищает от неработающих ключей:

1. **closed** — ключ работает нормально
2. **open** — после 3 ошибок (fail_count >= 3), ключ отключается на 5 минут
3. **half-open** — по истечении cooldown, делается пробный запрос. Успех → closed, ошибка → open

Состояние circuit breaker хранится в БД (`circuit_breakers` таблица) и sync между инстансами.

---

## Monitoring

### Prometheus Метрики

`GET /metrics` — Prometheus text exposition format. Доступные метрики:

- `api_hub_requests_total` — общее количество запросов
- `api_hub_errors_total` — количество ошибок (status >= 400)
- `api_hub_request_duration_ms` — латентность (гистограмма с buckets: 10, 50, 100, 250, 500, 1000, 5000, 10000 ms)
- `api_hub_keys_total` — количество ключей по статусу (ok/error/timeout/unknown)
- `api_hub_active_keys` — количество активных ключей
- `api_hub_circuit_breakers` — состояние circuit breaker (closed/open/half-open)
- `api_hub_health_checks_5m` — результаты health-check за 5 минут
- `api_hub_avg_health_latency_ms` — средняя латентность health-check (5 мин)
- `api_hub_requests_5m` — количество запросов за 5 минут
- `api_hub_avg_request_latency_ms` — средняя латентность запросов (5 мин)

### Grafana Dashboard

Рекомендуемый dashboard включает:

- Request rate (req/min) по провайдерам
- Error rate (% errors) по статусам
- P50/P95/P99 latency
- Circuit breaker states summary
- Key health status heatmap

### Алерты

Рекомендации для алертов:

- `api_hub_errors_total > 10` за 5 минут — warning
- `api_hub_circuit_breakers{state="open"} > 2` — warning
- `api_hub_active_keys < 5` — critical
- `api_hub_requests_5m == 0` более 30 минут — info (возможно нет трафика)

Подробнее — [docs/monitoring.md](docs/monitoring.md).

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

### Провайдеры (16 конфигов, 7 сидируются в БД)

**Бесплатные провайдеры (27 ключей от free-api-hunter):**

- **cerebras** (llm, 6 ключей) — Bearer, бесплатный
- **cloudflare** (llm, 1 ключ) — Bearer, бесплатный
- **cohere** (llm, 4 ключа) — Bearer, бесплатный
- **elevenlabs** (tts, 9 ключей) — Header, бесплатный
- **gemini** (llm, 1 ключ) — Query param, бесплатный
- **manus** (agent, 2 ключа) — Header, бесплатный
- **mistral** (llm, 2 ключа) — Bearer, бесплатный
- **ocr-space** (ocr, 1 ключ) — Header, бесплатный
- **pollinations** (image, 1 ключ) — none, бесплатный

**Платные/опенсорс провайдеры (сидируются в БД):**

- **openrouter** (llm) — Bearer, 20 req/min бесплатно
- **openai** (llm) — Bearer, платный
- **anthropic** (llm) — Header, платный
- **dadata** (geocode) — Header, 10000/день
- **abstractapi** (validate) — Query param, 100/мес
- **scraperapi** (scrape) — Query param, 1000/мес
- **pdfgeneratorapi** (generate) — Bearer, 3/день

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

8 тестовых модулей: `test_chat`, `test_circuit_breaker`, `test_health_check`, `test_health`, `test_keys`, `test_metrics`, `test_models`, `conftest`.
Тесты используют dependency override с тестовой БД (без реального PostgreSQL)..

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

- **✅ MVP** — FastAPI прокси, 7 провайдеров, базовые тесты
- **✅ v0.2** — 27 бесплатных ключей (9 провайдеров), 16 provider configs, circuit breaker, health-check, Prometheus метрики, rate limiting middleware, 8 тестовых модулей
- **v0.3** — lab-vault интеграция, per-agent квоты, API contract v2
- **v1.0** — Fallback между провайдерами, не-LLM эндпоинты, Redis rate limiting
- **v2.0** — Go gateway, Prometheus/Grafana, публичный продукт

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
