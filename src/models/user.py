"""Модель пользователя/агента."""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.config.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), nullable=False, unique=True)  # dominika, mangust, owl...
    email = Column(String(255), nullable=True, unique=True)
    api_key = Column(String(255), nullable=False, unique=True)  # ключ для доступа к API Hub
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
