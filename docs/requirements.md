# 📋 Требования к API Hub

**Версия:** 0.1 | **Дата:** 2026-06-19

---

## Функциональные требования

### Управление ключами
- `POST /keys` — загрузить API-ключ для провайдера
- `DELETE /keys/{id}` — удалить ключ
- `GET /keys` — список всех ключей (без значений, только метаданные)
- `GET /keys/{id}/status` — проверить работоспособность ключа
- Ключи хранятся зашифрованными (AES-256-GCM)
- В БД — только ссылки (ref), никогда plaintext

### Маршрутизация запросов
- `POST /v1/chat/completions` — единый эндпоинт для LLM (OpenAI-совместимый)
- `POST /v1/geocode` — геокодирование (DaData)
- `POST /v1/validate/{type}` — валидация (email, phone, IP через AbstractAPI)
- `POST /v1/scrape` — скрапинг (ScraperAPI)
- `POST /v1/generate/pdf` — генерация PDF
- Автоматический выбор провайдера по типу запроса
- Fallback: primary → secondary → stale cache

### Rate limiting
- Per-user — лимит на пользователя
- Per-provider — лимит на провайдера
- Per-endpoint — лимит на эндпоинт
- Алгоритм: token bucket или sliding window
- Хранение состояния в Redis

### Circuit breaker
- Порог: 5 ошибок за 60 сек → open
- Cooldown: 30 сек → half-open
- Успех → close
- Реализация: sony/gobreaker или hystrix-go

### Мониторинг
- Метрики: количество запросов, latency, ошибки, расход по ключам
- Хранение метрик в PostgreSQL
- Интеграция с Prometheus + Grafana
- Интеграция с myrmex-control

### Квоты
- Per-agent квоты на использование
- Настраиваемые лимиты по каждому провайдеру
- Уведомление при достижении 80% квоты

---

## Нефункциональные требования

### Производительность
- Latency добавки гейтвея: < 50ms (p99)
- Throughput: 1000 RPS на старте, масштабируемо
- Таймаут на провайдера: 30с (настраиваемый)

### Надёжность
- Uptime: 99.9%
- Health-check каждые 15с
- Graceful shutdown
- Fallback на прямые ключи при падении гейтвея

### Безопасность
- Все ключи шифруются AES-256-GCM
- Хранение в HashiCorp Vault
- В БД только ref, никогда plaintext
- API-ключи для доступа к самому гейтвею (JWT)
- Rate limiting на доступ к гейтвею

### Масштабируемость
- Горизонтальное масштабирование через K8s
- Stateless гейтвей (состояние в Redis)
- Добавление новых провайдеров без перезапуска (через конфиг/БД)

---

## MVP scope (1-2 недели)

**В MVP:**
- FastAPI прокси
- Маршрутизация: OpenRouter, OpenAI, Anthropic
- Единый `/v1/chat/completions` эндпоинт
- Ключи из lab-vault
- Базовый rate limiting (per-provider)
- Логирование запросов в PostgreSQL

**НЕ в MVP:**
- Веб-интерфейс
- Сложная маршрутизация (L1/L2/L3)
- Circuit breaker
- Per-agent квоты
- Интеграция с myrmex
- Не-LLM провайдеры
