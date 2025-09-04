from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from src.common.enums import UserRole


class UserBase(BaseModel):
    """Базовая схема для пользователя."""

    telegram_id: int
    name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    """Схема для создания нового пользователя."""

    role: UserRole


class UserUpdate(BaseModel):
    """Схема для обновления пользователя."""

    name: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserRead(UserBase):
    """Схема для чтения данных пользователя."""

    id: int
    role: UserRole

    class Config:
        orm_mode = True


class UserResponse(UserBase):
    """Схема для ответа с данными пользователя."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
