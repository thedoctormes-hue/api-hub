# ⚙️ Конфигурация провайдеров

**Версия:** 0.2 | **Дата:** 2026-06-28

---

## Обзор

API Hub поддерживает 16 првайдеров в 5 категориях. Конфигурация хранится в YAML-файлах (`config/providers/`) и сидируется в PostgreSQL при первом запуске.

---

## Типы провайдеров

**llm** — языковые модели (chat completions)
**geocode** — геокодирование адресов
**validate** — валидация email/телефонов
**scrape** — веб-скрапинг
**generate** — генерация документов (PDF)
**ocr** — оптическое распознавание текста
**tts** — текст в речь
**image** — генерация изображений
**agent** — AI-агенты

---

## Аутентификация

**bearer** — заголовок `Authorization: Bearer <key>`
**header** — произвольный заголовок (например, `x-api-key`)
**query_param** — ключ передаётся как query-параметр

---

## Полный список провайдеров (16)

### LLM (8 провайдеров)

**openrouter** (бесплатный tier)
- Base URL: `https://openrouter.ai/api/v1`
- Auth: bearer
- Rate limit: 20 req/min
- 200+ моделей через единый API

**openai**
- Base URL: `https://api.openai.com/v1`
- Auth: bearer
- Rate limit: 60 req/min

**anthropic**
- Base URL: `https://api.anthropic.com`
- Auth: header (`x-api-key`)
- Rate limit: 50 req/min

**cerebras** (бесплатный)
- Base URL: `https://api.cerebras.ai/v1`
- Auth: bearer
- Бесплатный tier через free-api-hunter

**cloudflare** (бесплатный)
- Base URL: `https://api.cloudflare.com/client/v1`
- Auth: bearer
- Workers AI модели

**cohere** (бесплатный)
- Base URL: `https://api.cohere.com/v1`
- Auth: bearer
- Command R, Embed модели

**gemini** (бесплатный)
- Base URL: `https://generativelanguage.googleapis.com/v1beta`
- Auth: query_param
- Google Gemini модели

**mistral** (бесплатный)
- Base URL: `https://api.mistral.ai/v1`
- Auth: bearer
- Mistral 7B, Mixtral модели

### Геокодирование (1 провайдер)

**dadata**
- Base URL: `https://suggestions.dadata.ru/suggestions/api/4_1/rs`
- Auth: header (`Authorization: Token <key>`)
- Rate limit: 30 req/min

### Валидация (1 провайдер)

**abstractapi**
- Base URL: `https://emailvalidation.abstractapi.com/v1`
- Auth: query_param (`api_key`)
- Rate limit: 10 req/min

### Скрапинг (1 провайдер)

**scraperapi**
- Base URL: `https://api.scraperapi.com`
- Auth: query_param (`api_key`)
- Rate limit: 10 req/min

### Генерация PDF (1 провайдер)

**pdfgeneratorapi**
- Base URL: `https://us1.pdfgeneratorapi.com/api/v4`
- Auth: bearer
- Rate limit: 5 req/min

### OCR (1 провайдер)

**ocr-space** (бесплатный)
- Base URL: `https://api.ocr.space/parse/image`
- Auth: header
- Распознавание текста с изображений

### TTS (1 провайдер)

**elevenlabs** (бесплатный)
- Base URL: `https://api.elevenlabs.io/v1`
- Auth: header
- Синтез речи

### Генерация изображений (1 провайдер)

**pollinations** (бесплатный)
- Base URL: `https://image.pollinations.ai/prompt`
- Auth: none (публичный API)
- Генерация изображений по текстовому описанию

### AI-агент (1 провайдер)

**manus** (бесплатный)
- Base URL: `https://api.manus.ai/v2`
- Auth: header
- Агентский API для выполнения задач

---

## Маршрутизация

Приоритет выбора провайдера:
1. Фильтрация по типу запроса (только `llm` для `/v1/chat/completions`)
2. Только активные ключи (`is_active=True`)
3. Только активные провайдеры (`is_active=True`)
4. Сортировка по `rate_limit` (desc) — предпочитаем менее загруженных

---

## Circuit Breaker

Каждый ключ имеет circuit breaker:
- **closed** — нормальная работа
- **open** — 3 ошибки подряд → cooldown 5 минут
- **half-open** — после cooldown, пробный запрос. Успех → closed, ошибка → open

---

## Добавление нового провайдера

1. Создать YAML-файл в `config/providers/`
2. Добавить запись в `DEFAULT_PROVIDERS` в `src/config/database.py`
3. Перезапустить сервис
