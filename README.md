# 🔌 API Hub

> **⚠️ DEPRECATED / MERGED**
>
> Этот проект полностью поглощён в **[free-api-hunter](https://github.com/thedoctormes-hue/free-api-hunter)**.
> Весь функционал API-шлюза перенесён в Go-реализацию вместе с маршрутизацией, rate limiting, health checks, scan endpoint, metrics и веб-интерфейсом.
>
> **Этот репозиторий заархивирован и не поддерживается.**
> Если вам нужен API-шлюз — используйте [free-api-hunter](https://github.com/thedoctormes-hue/free-api-hunter).

---

<details>
<summary>Архивная документация (2026-06-19 — 2026-06-29)</summary>

## Концепт

API-Hub — единый API-шлюз для всех внешних API. Пользователь загружает ключи — получает один эндпоинт для всего.

**Ключевая идея:** все существующие решения (OpenRouter, LiteLLM) — только про LLM. API-Hub — универсальный шлюз для любых API.

## Стек (Python MVP)

- **FastAPI** — async web framework
- **SQLAlchemy 2.0 + asyncpg** — ORM и драйвер PostgreSQL
- **PostgreSQL** — хранение конфигов, ключей (refs), логов, квот
- **Redis** (планировался) — rate limiting, circuit breaker state
- **HashiCorp Vault** (планировался) — шифрование ключей

## Статус

- ✅ MVP — FastAPI прокси, 7 провайдеров, 6 моделей, тесты
- ✅ Поглощён free-api-hunter (Go, SQLite, prod-ready)

## Roadmap (архивный)

| Этап | Что | Статус |
|---|---|---|
| ✅ MVP | FastAPI прокси, 7 провайдеров | Выполнен, поглощён |
| v2 | lab-vault интеграция, circuit breaker | Реализован в free-api-hunter (Go) |
| v2 | Fallback, не-LLM эндпоинты | Реализован в free-api-hunter (Go) — 80+ CF Workers AI моделей |
| v3 | Go gateway, Prometheus/Grafana | Реализован в free-api-hunter (prod-ready) |

## Связь с проектами колонии

| Проект | Роль |
|---|---|
| **lab-vault** | Хранилище ключей (source of truth) |
| **free-api-hunter** | Поглотил API-Hub, теперь единый шлюз |
| **myrmex-control** | Метрики, мониторинг, rate limits |

---

*Этот README сохранён для истории. Последний коммит: 19 июня 2026.*
</details>

