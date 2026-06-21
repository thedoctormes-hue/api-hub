"""Модель квоты пользователя на провайдер."""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.config.database import Base


class Quota(Base):
    __tablename__ = "quotas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
    period = Column(String(16), nullable=False)  # day, month, total
    limit_count = Column(Integer, nullable=False)  # лимит запросов
    limit_tokens = Column(Integer, nullable=True)  # лимит токенов (для LLM)
    used_count = Column(Integer, nullable=False, default=0)
    used_tokens = Column(Integer, nullable=False, default=0)
    reset_at = Column(DateTime(timezone=True), nullable=False)  # когда сбрасывается квота
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
