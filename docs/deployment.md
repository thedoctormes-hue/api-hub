# 🚀 Руководство по деплою

**Версия:** 0.2 | **Дата:** 2026-06-28

---

## Требования

- Docker 24.0+ и Docker Compose v2.20+
- 2 GB RAM минимум
- 1 GB дискового пространства
- PostgreSQL 15+ (или используйте встроенный контейнер)

---

## Быстрый старт с Docker

```bash
# Клонировать репозиторий
git clone <repo-url> LabDoctorM
cd LabDoctorM/projects/api-hub

# Запусь всех сервисов
docker-compose up -d --build

# Проверить что поднялось
curl http://localhost:8000/health
```

---

## Конфигурация

### docker-compose.yml

```yaml
version: "3.8"

services:
  api-hub:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/apihub
      - MASTER_KEY=${MASTER_KEY:-change-me-in-production}
      - LOG_LEVEL=INFO
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=apihub
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    depends_on:
      - api-hub
    restart: unless-stopped
    profiles:
      - monitoring

volumes:
  pgdata:
```

### Переменные окружения

| Переменная | По умолчанию | Описание | Обязательная |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/apihub` | URL PostgreSQL | да |
| `MASTER_KEY` | `dev-master-key` | Мастер-ключ для API | да (прод) |
| `APP_VERSION` | `0.2.0` | Версия сервиса | нет |
| `LOG_LEVEL` | `INFO` | Уровень логирования (DEBUG, INFO, WARNING, ERROR) | нет |
| `APP_ENV` | `production` | Окружение (development, staging, production) | нет |

---

## Запуск без Docker

### Локальная разработка

```bash
# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Поднять PostgreSQL (например, через Docker)
docker run -d --name api-hub-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=apihub \
  -p 5432:5432 postgres:15-alpine

# Экспорт переменных
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/apihub
export MASTER_KEY=dev-secret-key

# Запуск
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 --log-level info
```

### Production запуск

```bash
# Установить gunicorn
pip install gunicorn

# Запуск с воркерами
gunicorn src.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

---

## Миграции базы данных

При первом запуске таблицы создаются автоматически, провайдеры сидируются из `DEFAULT_PROVIDERS`.

```bash
# Если нужен ручной сброс
docker-compose exec api-hub python3 -c \
  "from src.config.database import init_db; import asyncio; asyncio.run(init_db())"
```

---

## Мониторинг

### Health Endpoints

```
GET /health          — базовый health check
GET /health/keys     — статус всех ключей и circuit breaker
GET /metrics         — Prometheus метрики
```

### Prometheus

```bash
# Запуск с мониторингом
docker-compose --profile monitoring up -d

# Prometheus доступен на http://localhost:9090

# Target: http://api-hub:8000/metrics
```

### Ключевые метрики

- `api_hub_requests_total` — общее количество запросов
- `api_hub_errors_total` — количество ошибок (status >= 400)
- `api_hub_request_duration_ms` — латентность (гистограмма)
- `api_hub_keys_total` — количество ключей по статусу
- `api_hub_active_keys` — активных ключей
- `api_hub_circuit_breakers` — состояние circuit breaker
- `api_hub_health_checks_5m` — health-checkи за 5 минут

---

## Безопасность

1. **Измените MASTER_KEY** — используйте случайную строку длиной 32+ символов
2. **Не коммитьте .env** — добавьте в `.gitignore`
3. **Используйте HTTPS** — разверните за reverse proxy (nginx/traefik)
4. **Ограничьте доступ к /metrics** — только для Prometheus
5. **PostgreSQL** — используйте отдельного пользователя с минимальными правами

---

## Устранение проблем

### Контейнер не поднялся

```bash
# Логи
docker-compose logs api-hub
docker-compose logs db

# Проверка БД
docker-compose exec db psql -U postgres -c "SELECT 1"
```

### Ошибка подключения к БД

Проверьте `DATABASE_URL` — формат:
```
postgresql+asyncpg://<user>:<password>@<host>:<port>/<dbname>
```

### Метрики не доступны

```bash
# Проверить что endpoint отвечает
docker-compose exec api-hub curl -s http://localhost:8000/metrics

# Проверить Prometheus target
curl http://localhost:9090/api/v1/targets
```

---

## Масштабирование

Для горизонтального масштабирования:
1. Поднять несколько экземпляров `api-hub`
2. Поставить nginx/haproxy перед ними
3. Circuit breaker state хранится в PostgreSQL — синхронизирован между инстансами
4. Для rate limiting — добавить Redis (в планах v0.3)
