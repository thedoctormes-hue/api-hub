# ⚙️ Конфигурация провайдеров

**Версия:** 0.1 | **Дата:** 2026-06-19

---

## Формат конфигурации

Провайдеры описываются в YAML-файлах в `config/providers/` и загружаются при старте.

### Структура файла

```yaml
# config/providers/openrouter.yaml
name: openrouter
type: llm
base_url: https://openrouter.ai/api/v1
auth:
  type: bearer
  header: Authorization
  prefix: "Bearer "
rate_limit:
  requests_per_minute: 20
  requests_per_day: 200
timeout: 30
retry:
  count: 3
  delay_ms: 1000
  backoff: exponential
models:
  - id: openrouter/auto
    name: Auto
    type: chat
    max_tokens: 128000
  - id: anthropic/claude-sonnet-4
    name: Claude Sonnet 4
    type: chat
    max_tokens: 200000
health_check:
  enabled: true
  interval_sec: 15
  endpoint: /models
```

---

## Типы провайдеров

### LLM
```yaml
type: llm
base_url: https://...
auth:
  type: bearer
models:
  - id: model-id
    name: Human Name
    type: chat | completion
    max_tokens: 128000
```

### Geocode
```yaml
type: geocode
base_url: https://suggestions.dadata.ru/suggestions/api/4_1/rs
auth:
  type: header
  header: Authorization
  prefix: "Token "
```

### Validate
```yaml
type: validate
base_url: https://emailvalidation.abstractapi.com/v1
auth:
  type: query_param
  param: api_key
```

### Scrape
```yaml
type: scrape
base_url: https://api.scraperapi.com
auth:
  type: query_param
  param: api_key
```

### Generate
```yaml
type: generate
base_url: https://us1.pdfgeneratorapi.com/api/v4
auth:
  type: bearer
```

---

## Дефолтные провайдеры (предзаполненные)

### LLM
| Провайдер | Base URL | Auth | Бесплатный tier |
|---|---|---|---|
| OpenRouter | openrouter.ai/api/v1 | bearer | 20 req/min, 200/day |
| OpenAI | api.openai.com/v1 | bearer | нет |
| Anthropic | api.anthropic.com | header (x-api-key) | нет |
| Groq | api.groq.com/openai/v1 | bearer | есть |
| Mistral | api.mistral.ai/v1 | bearer | есть |
| Together AI | api.together.xyz/v1 | bearer | есть ($25 credit) |
| Google AI | generativelanguage.googleapis.com | query_param | есть |

### Гео
| Провайдер | Base URL | Auth | Бесплатный tier |
|---|---|---|---|
| DaData | suggestions.dadata.ru | header (Token) | 10000 день |

### Валидация
| Провайдер | Base URL | Auth | Бесплатный tier |
|---|---|---|---|
| AbstractAPI | emailvalidation.abstractapi.com | query_param | 100/мес |

### Скрапинг
| Провайдер | Base URL | Auth | Бесплатный tier |
|---|---|---|---|
| ScraperAPI | api.scraperapi.com | query_param | 1000/мес |

### Генерация
| Провайдер | Base URL | Auth | Бесплатный tier |
|---|---|---|---|
| PDFGeneratorAPI | us1.pdfgeneratorapi.com | bearer | 3/день |

---

## Добавление нового провайдера

1. Создать YAML-файл в `config/providers/`
2. Описать формат запроса/ответа
3. Добавить маппинг в `src/router/provider_map.go` (или аналог)
4. Перезапустить сервис (или отправить SIGHUP для hot-reload)

---

## Приоритеты и fallback

Для каждого типа запроса можно задать цепочку провайдеров:

```yaml
# config/routing.yaml
routing:
  llm:
    primary: openrouter
    fallbacks:
      - groq
      - mistral
      - together
  geocode:
    primary: dadata
    fallbacks: []
  validate:
    primary: abstractapi
    fallbacks: []
  scrape:
    primary: scraperapi
    fallbacks: []
  generate:
    primary: pdfgeneratorapi
    fallbacks: []
```
