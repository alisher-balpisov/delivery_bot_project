from datetime import datetime
from typing import Literal

from backend.src.common.enums import UserRole, UserStatus
from backend.src.common.utils.validaters import Phone
from backend.src.core.validators import validate_no_malicious_content, validate_string_length
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserBase(BaseModel):
    """Базовая схема для пользователя."""

    telegram_id: int
    name: str | None = Field(None, max_length=100)
    phone: Phone | None = Field(None, max_length=20)
    role: UserRole

    model_config = ConfigDict(from_attributes=True)

    @field_validator("name")
    def validate_name_input(cls, v: str | None):
        return validate_no_malicious_content(validate_string_length(v, max_length=100))


class UserCreate(UserBase):
    """Схема для создания нового пользователя."""

    ...


class UserResponse(UserBase):
    """Схема для ответа с данными пользователя."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRead(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    role: UserRole | None
    status: UserStatus

    model_config = ConfigDict(from_attributes=True)


class UserCreateWithoutPassword(BaseModel):
    """Схема для регистрации пользователя без пароля - только данные для сбора после активации кода."""

    name: str | None = Field(None, max_length=100)
    phone: Phone | None = Field(None, max_length=20)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("name")
    def validate_name_input(cls, v):
        return validate_no_malicious_content(validate_string_length(v, max_length=100))


class ShopUserUpdate(BaseModel):
    """Схема для обновления профиля магазина."""

    role: Literal[UserRole.SHOP]
    name: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=512)
    address_link: str | None = Field(None, max_length=512)
    phone_number: list[str] | None = None

    model_config = ConfigDict(from_attributes=True)


class CourierUserUpdate(BaseModel):
    """Схема для обновления профиля курьера."""

    role: Literal[UserRole.COURIER]
    full_name: str | None = Field(None, max_length=255)
    phone_number: list[str] | None = None
    photo_id: str | None = Field(None, max_length=255)

    model_config = ConfigDict(from_attributes=True)


UserUpdate = ShopUserUpdate | CourierUserUpdate
