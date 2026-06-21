"""Модель ключа пользователя для провайдера (ссылка на Vault)."""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.config.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
    key_ref = Column(String(255), nullable=False)  # ссылка на ключ в Vault (НЕ сам ключ!)
    key_alias = Column(String(64), nullable=False)  # человекочитаемое имя: "основной", "запасной"
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(16), nullable=True)  # ok, error, rate_limited
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
