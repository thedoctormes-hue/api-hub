# 📝 Краткое резюме: API Hub

**Что это:** Единый API-шлюз для всех внешних API. Пользователь загружает свои ключи — получает один эндпоинт для всего.

**Почему это нужно:** Хаос с ключами у 8 агентов колонии → нужен контроль, мониторинг, fallback.

**Архитектура:**
- **MVP:** FastAPI + lab-vault + `/v1/chat/completions`
- **Продакшен:** Go + PostgreSQL + Redis + HashiCorp Vault
- **Мониторинг:** myrmex-control + Prometheus/Grafana

**Провайдеры:**
- LLM: OpenRouter, OpenAI, Anthropic, Google, Groq, Mistral, Together AI (16+ бесплатных)
- Гео: DaData
- Валидация: AbstractAPI
- Скрапинг: ScraperAPI
- Генерация: PDFGeneratorAPI

**Риски:** единая точка отказа, безопасность ключей, per-agent квоты → митигация через health-check, Vault, квоты.

**План:** MVP (2 нед) → v2 (мес) → v3 (3 мес, публичный продукт)

**Документы:** см. `docs/` — ADR, требования, модель данных, API-контракт, конфиги, дорожная карта.
