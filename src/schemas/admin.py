from typing import Literal

from pydantic import BaseModel, Field, field_validator


class OneTimeCodeBase(BaseModel):
    """Базовая схема для одноразового кода."""

    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    user_role: Literal["shop", "courier", "admin"] = Field(
        ..., description="User role for the code"
    )

    @field_validator("code")
    @classmethod
    def validate_code_format(cls, v):
        """Валидировать, что код состоит только из цифр."""
        if not v.isdigit():
            raise ValueError("Code must contain only digits")
        return v


class OneTimeCodeCreate(BaseModel):
    """Схема для запроса на создание кода (например, от админа)."""

    telegram_id: int = Field(..., gt=0, description="Valid Telegram user ID")
    user_role: Literal["shop", "courier", "admin"] = Field(..., description="User role to assign")

    @field_validator("telegram_id")
    @classmethod
    def validate_telegram_id(cls, v):
        """Валидировать корректность Telegram ID."""
        if v <= 0:
            raise ValueError("Telegram ID must be positive")
        return v


class OneTimeCodeRead(OneTimeCodeBase):
    """Схема для чтения кода (например, из Redis)."""

    is_used: bool = False


class AdminVerificationRequest(BaseModel):
    """Схема для запроса верификации администратора."""

    telegram_id: int = Field(..., gt=0, description="Admin's Telegram ID")
    token: str | None = None  # Optional authentication token for additional security
