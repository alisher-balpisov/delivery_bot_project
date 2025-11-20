from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.src.common.enums import DisputeResolutionType, UserRole


class RegistrationCodeBase(BaseModel):
    code: str = Field(..., max_length=20)
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class RegistrationCodeResponse(RegistrationCodeBase):
    id: int
    is_used: bool
    used_by_user_id: int | None = None
    created_at: datetime
    expires_at: datetime

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

    model_config = ConfigDict(from_attributes=True)


class SystemStatsResponse(BaseModel):
    """Схема для системной статистики."""

    total_users: int
    total_admins: int
    total_shops: int
    total_couriers: int
    total_orders: int
    active_orders: int
    completed_orders: int
    cancelled_orders: int
    total_disputes: int
    unresolved_disputes: int
