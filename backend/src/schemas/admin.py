from datetime import datetime

from backend.src.common.enums import UserRole
from pydantic import BaseModel, ConfigDict, Field


class RegistrationCodeBase(BaseModel):
    code: str = Field(..., max_length=20)
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class RegistrationCodeCreate(RegistrationCodeBase):
    pass


class RegistrationCodeResponse(RegistrationCodeBase):
    id: int
    is_used: bool
    user_id: int | None = None
    created_at: datetime
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CodeActivationRequest(BaseModel):
    """Схема для активации одноразового кода регистрации."""

    telegram_id: int
    code: str
    role: UserRole | None = None

    model_config = ConfigDict(from_attributes=True)


class CodeActivationResponse(BaseModel):
    """Модель ответа для активации кода регистрации."""

    success: bool
    user_id: int | None = None
    role: str | None = None
    attempts_left: int | None = None
    blocked: bool = False
    detail: str | None = None
