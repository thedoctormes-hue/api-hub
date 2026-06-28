"""
API Hub — единый API-шлюз для всех внешних API.
MVP: FastAPI прокси с маршрутизацией по провайдерам.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.config.database import init_db, close_db
from src.middleware.rate_limit import RateLimitMiddleware
from src.routes import keys, chat, models, health, metrics, metrics
from src.middleware.metrics import MetricsMiddleware
from src.config.settings import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при старте, закрытие при остановке."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    description="Единый API-шлюз для всех внешних API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimitMiddleware, calls_per_minute=settings.DEFAULT_RATE_LIMIT_PER_MINUTE)

# Metrics
app.add_middleware(MetricsMiddleware)

# Роуты
app.include_router(health.router, tags=["Health"])
app.include_router(metrics.router, tags=["Metrics"])
app.include_router(keys.router, prefix="/keys", tags=["Keys"])
app.include_router(chat.router, prefix="/v1", tags=["LLM"])
app.include_router(models.router, prefix="/v1", tags=["Models"])
app.include_router(metrics.router, tags=["Metrics"])
