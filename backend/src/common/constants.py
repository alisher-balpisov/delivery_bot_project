from collections.abc import Awaitable, Callable
from typing import Any

from backend.src.auth.dependencies import User
from backend.src.common.enums import OrderStatus

# Импорт констант валидации из нового модуля
from backend.src.common.validation import (
    COMMISSION,  # deprecated, используйте CommissionRules
    VALIDATION,  # deprecated, используйте ValidationRules
    CommissionRules,
    ValidationRules,
)
from backend.src.models.order import Order
from pydantic import BaseModel, Field

# ==============================================================================
# Deprecated константы (используйте ValidationRules и CommissionRules)
# ==============================================================================
# VALIDATION и COMMISSION остаются для обратной совместимости
# Рекомендуется мигрировать на ValidationRules и CommissionRules

# ==============================================================================
# Константы времени
# ==============================================================================
SECONDS_IN_MINUTE = 60
MINUTES_IN_HOUR = 60
HOURS_IN_DAY = 24
MAX_ALLOWED_DATE_FOR_ORDER = 365

# ==============================================================================
# Типы
# ==============================================================================

type UpdatePayload = dict[str, Any]

# ==============================================================================
# Type Aliases для проверок прав доступа
# ==============================================================================

UpdatePermissionCheck = Callable[[User, Order, UpdatePayload], Awaitable[None]]
RetrievePermissionCheck = Callable[[User, Order], Awaitable[None]]

# ==============================================================================
# Константы для заказов
# ==============================================================================

COURIER_ALLOWED_FIELDS = {"status", "courier_notes", "completion_notes"}
FINAL_STATUSES = {OrderStatus.COMPLETED, OrderStatus.CANCELED}
ACTIVE_STATUSES_FOR_COURIER = [
    OrderStatus.PENDING_COURIER,
    OrderStatus.COURIER_EN_ROUTE,
    OrderStatus.DELIVERING,
    OrderStatus.AWAITING_CONFIRMATION,
    OrderStatus.DISPUTED,
]
ALLOWED_STATUSES_FOR_CREATE_DISPUTE = [
        OrderStatus.COURIER_EN_ROUTE,
        OrderStatus.DELIVERING,
        OrderStatus.AWAITING_CONFIRMATION,
    ]


# ==============================================================================
# Общая модель пагинированного ответа
# ==============================================================================


class PaginatedResponse[T](BaseModel):
    """Универсальная модель для пагинированных ответов."""

    total: int = Field(..., description="Общее количество элементов")
    items: list[T] = Field(..., description="Список элементов на текущей странице")


# ==============================================================================
# Экспорт
# ==============================================================================

__all__ = [
    "COMMISSION",
    "COURIER_ALLOWED_FIELDS",
    "FINAL_STATUSES",
    "HOURS_IN_DAY",
    "MINUTES_IN_HOUR",
    "SECONDS_IN_MINUTE",
    "VALIDATION",
    "CommissionRules",
    "PaginatedResponse",
    "RetrievePermissionCheck",
    "UpdatePayload",
    "UpdatePermissionCheck",
    "ValidationRules",
]
