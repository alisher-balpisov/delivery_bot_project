from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.common.enums import UserRole
from src.common.utils import Phone
from src.core.validators import validate_no_malicious_content, validate_string_length


class UserBase(BaseModel):
    """Базовая схема для пользователя."""

    telegram_id: int
    name: str | None = Field(None, max_length=100)
    phone: Phone | None = Field(None, max_length=20)
    role: UserRole

    model_config = ConfigDict(from_attributes=True)

    @field_validator("name")
    def validate_name_input(cls, v):
        return validate_no_malicious_content(validate_string_length(v, max_length=100))


class UserCreate(UserBase):
    """Схема для создания нового пользователя."""

    role: UserRole


class UserUpdate(BaseModel):
    """Схема для обновления пользователя."""

    name: str | None = None
    phone: Phone | None = None

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
