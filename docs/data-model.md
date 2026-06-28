# 🗄️ Модель данных

**Версия:** 0.2 | **Дата:** 2026-06-27

---

## Сущности

### User (пользователь / агент)
```
id          UUID PK
name        VARCHAR(64)     -- имя агента: dominika, mangust, owl...
email       VARCHAR(255)    -- опционально
api_key     VARCHAR(255)    -- ключ для доступа к API Hub
created_at  TIMESTAMP
updated_at  TIMESTAMP
is_active   BOOLEAN default true
```

### Provider (провайдер)
```
id              UUID PK
name            VARCHAR(64)     -- openrouter, openai, dadata, abstractapi...
type            VARCHAR(32)     -- llm, geocode, validate, scrape, generate
base_url        VARCHAR(512)    -- URL API провайдера
auth_type       VARCHAR(32)     -- bearer, header, query_param
auth_key_name   VARCHAR(64)     -- название заголовка/параметра для ключа
rate_limit      INTEGER         -- лимит запросов в минуту
timeout_sec     INTEGER default 30
retry_count     INTEGER default 3
retry_delay_ms  INTEGER default 1000
is_active       BOOLEAN default true
is_free         BOOLEAN default false  -- бесплатный провайдер
free_source     VARCHAR(32)          -- free_api_hunter, manual
config          JSONB           -- доп. настройки провайдера
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### ApiKey (ключ пользователя для провайдера)
```
id              UUID PK
user_id         UUID FK -> User
provider_id     UUID FK -> Provider
key_ref         VARCHAR(255)    -- ссылка на ключ в Vault (НЕ сам ключ!)
key_alias       VARCHAR(64)     -- человекочитаемое имя: "основной", "запасной"
source          VARCHAR(32)     -- manual, free_api_hunter, imported
verified_at     TIMESTAMP       -- время последней верификации
credits_balance INTEGER         -- остаток кредитов/квот
rate_limit_type VARCHAR(32)     -- requests_per_day, tokens_per_minute, credits_total
is_active       BOOLEAN default true
last_used_at    TIMESTAMP
last_status     VARCHAR(16)     -- ok, error, rate_limited
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### Quota (квота пользователя на провайдер)
```
id              UUID PK
user_id         UUID FK -> User
provider_id     UUID FK -> Provider
period          VARCHAR(16)     -- day, month, total
limit_count     INTEGER         -- лимит запросов
limit_tokens    INTEGER         -- лимит токенов (для LLM)
used_count      INTEGER default 0
used_tokens     INTEGER default 0
reset_at        TIMESTAMP       -- когда сбрасывается квота
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### RequestLog (лог запросов)
```
id              UUID PK
user_id         UUID FK -> User
provider_id     UUID FK -> Provider
api_key_id      UUID FK -> ApiKey
endpoint        VARCHAR(255)    -- куда ушёл запрос
method          VARCHAR(8)      -- POST, GET...
status_code     INTEGER         -- ответ провайдера
latency_ms      INTEGER         -- время ответа
tokens_in       INTEGER         -- входящие токены (LLM)
tokens_out      INTEGER         -- исходящие токены (LLM)
error           TEXT            -- текст ошибки если есть
created_at      TIMESTAMP
```

### CircuitBreaker (состояние circuit breaker)
```
id              UUID PK
provider_id     UUID FK -> Provider
api_key_id      UUID FK -> ApiKey
state           VARCHAR(16)     -- closed, open, half-open
fail_count      INTEGER default 0
last_failure    TIMESTAMP
last_success    TIMESTAMP
opened_at       TIMESTAMP
half_open_at    TIMESTAMP
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

---

### KeyHealthLog (лог здоровья ключей)
```
id              UUID PK
api_key_id      UUID FK -> ApiKey
checked_at      TIMESTAMP
status          VARCHAR(16)     -- ok, error, rate_limited, timeout
latency_ms      INTEGER
quota_remaining INTEGER
error_text      TEXT
created_at      TIMESTAMP
```

## Индексы

```
-- Быстрый поиск ключей пользователя
CREATE INDEX idx_api_keys_user ON ApiKey(user_id, is_active);

-- Логи по пользователю и времени
CREATE INDEX idx_request_log_user_time ON RequestLog(user_id, created_at DESC);

-- Логи по провайдеру и времени
CREATE INDEX idx_request_log_provider_time ON RequestLog(provider_id, created_at DESC);

-- Квоты: быстрый поиск текущих
CREATE INDEX idx_quotas_user_provider ON Quota(user_id, provider_id, period);

-- Circuit breaker: быстрый поиск по провайдеру+ключу
CREATE INDEX idx_circuit_breaker ON CircuitBreaker(provider_id, api_key_id);

-- KeyHealthLog: быстрый поиск по ключу и времени
CREATE INDEX idx_health_log_key_time ON KeyHealthLog(api_key_id, checked_at DESC);
CREATE INDEX idx_health_log_status ON KeyHealthLog(status);
```

---

## Диаграмма связей

```
User 1───* ApiKey *───1 Provider
User 1───* Quota  *───1 Provider
User 1───* RequestLog
Provider 1───* RequestLog
Provider 1───* CircuitBreaker
ApiKey 1───* CircuitBreaker
ApiKey 1───* RequestLog
```

---

## Миграции

Все миграции через `golang-migrate` или `alembic` (в зависимости от стека).

Порядок создания таблиц:
1. User
2. Provider
3. ApiKey
4. Quota
5. RequestLog
6. CircuitBreaker
