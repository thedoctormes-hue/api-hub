"""Модель провайдера."""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.config.database import Base


class Provider(Base):
    __tablename__ = "providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), nullable=False, unique=True)  # openrouter, openai, dadata...
    type = Column(String(32), nullable=False)  # llm, geocode, validate, scrape, generate
    base_url = Column(String(512), nullable=False)
    auth_type = Column(String(32), nullable=False)  # bearer, header, query_param
    auth_key_name = Column(String(64), nullable=False)  # название заголовка/параметра для ключа
    rate_limit = Column(Integer, nullable=False)  # лимит запросов в минуту
    timeout_sec = Column(Integer, nullable=False, default=30)
    retry_count = Column(Integer, nullable=False, default=3)
    retry_delay_ms = Column(Integer, nullable=False, default=1000)
    is_active = Column(Boolean, default=True)
    is_free = Column(Boolean, nullable=False, default=False)
    free_source = Column(String(32), nullable=True)  # free_api_hunter, manual
    health_check_endpoint = Column(String(256), nullable=True)  # кастомный health endpoint
    config = Column(JSON, nullable=True)  # доп. настройки провайдера
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
