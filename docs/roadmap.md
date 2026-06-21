# 🗺️ Roadmap

**Версия:** 0.1 | **Дата:** 2026-06-19

---

## Этапы разработки

### Этап 0: Подготовка (сделано)
- [x] Архитектурные решения от агентов колонии
- [x] ADR-001: создание API Hub
- [x] Требования
- [x] Модель данных
- [x] API-контракт
- [x] Конфигурация провайдеров

### Этап 1: MVP (1-2 недели)
- [ ] FastAPI прокси
- [ ] Маршрутизация по провайдерам LLM (OpenRouter, OpenAI, Anthropic)
- [ ] Единый эндпоинт `/v1/chat/completions`
- [ ] Интеграция с lab-vault для хранения ключей
- [ ] Базовое логирование запросов в PostgreSQL
- [ ] Rate limiting per-provider (простой)
- [ ] Dockerfile и docker-compose.yml для локального запуска

### Этап 2: v2 (месяц)
- [ ] Rate limiting per-user, per-endpoint
- [ ] Per-agent квоты
- [ ] Интеграция с myrmex-control для метрик
- [ ] Fallback на free-api-hunter и бесплатные провайдеры
- [ ] Circuit breaker
- [ ] Health-check endpoints
- [ ] Веб-интерфейс для управления ключами (опционально)

### Этап 3: v3 (3 месяца)
- [ ] Переписать на Go для продакшена
- [ ] Публичный продукт: документация, API keys для внешних пользователей
- [ ] Биллинг и тарификация
- [ ] Мониторинг: Prometheus + Grafana дашборды
- [ ] Автомасштабирование в Kubernetes
- [ ] Поддержка не-LLM провайдеров (DaData, AbstractAPI, ScraperAPI, PDFGeneratorAPI)
- [ ] Hot-reload конфигурации провайдеров

### Этап 4: v4 и далее
- [ ] A/B тестирование провайдеров
- [ ] Smart routing на основе latency и стоимости
- [ ] Кеширование ответов
- [ ] Batch запросы
- [ ] WebSocket поддержка
- [ ] Плагин-система для кастомных провайдеров

---

## Технические долги и улучшения
- [ ] Добавление тестов (unit, integration)
- [ ] Настройка CI/CD (GitHub Actions)
- [ ] Security audit
- [ ] Load testing
- [ ] Documentation generation (Swagger/OpenAPI)
- [ ] Multi-tenancy поддержка
- [ ] Audit log для соответствия требованиям
