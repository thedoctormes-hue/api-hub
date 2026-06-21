"""Модель лога запросов."""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.config.database import Base


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False)
    endpoint = Column(String(255), nullable=False)  # куда ушёл запрос
    method = Column(String(8), nullable=False)  # POST, GET...
    status_code = Column(Integer, nullable=False)  # ответ провайдера
    latency_ms = Column(Integer, nullable=False)  # время ответа
    tokens_in = Column(Integer, nullable=True)  # входящие токены (LLM)
    tokens_out = Column(Integer, nullable=True)  # исходящие токены (LLM)
    error = Column(Text, nullable=True)  # текст ошибки если есть
    created_at = Column(DateTime(timezone=True), server_default=func.now())
