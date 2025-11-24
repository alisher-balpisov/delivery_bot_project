from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.src.common.enums import UserRole


class RegistrationCodeResponse(BaseModel):
    code: str = Field(..., max_length=20)
    role: UserRole
    id: int
    is_used: bool
    used_by_user_id: int | None = None
    created_at: datetime
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateRegistrationCodeRequest(BaseModel):
    """Схема запроса для создания кода регистрации."""

    role: UserRole


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
    orders_today: int
    active_couriers: int
