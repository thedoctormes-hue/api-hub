"""Модель лога здоровья API-ключей."""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.config.database import Base


class KeyHealthLog(Base):
    __tablename__ = "key_health_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False)
    checked_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status = Column(String(16), nullable=False)  # ok, error, rate_limited, timeout
    latency_ms = Column(Integer, nullable=True)
    quota_remaining = Column(Integer, nullable=True)
    error_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
