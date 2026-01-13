from collections.abc import Awaitable, Callable
from typing import Any

from backend.src.auth.dependencies import User
from backend.src.common.enums import OrderStatus, UserRole

# Импорт констант валидации из нового модуля
from backend.src.common.validation import (
    COMMISSION,  # deprecated, используйте CommissionRules
    VALIDATION,  # deprecated, используйте ValidationRules
    CommissionRules,
    ValidationRules,
)
from backend.src.models.order import Order
from backend.src.orders.schemas import (
    OrderResponseForAdmin,
    OrderResponseForCourier,
    OrderResponseForShop,
)
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

type OrderResponseSchema = OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier
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

# ==============================================================================
# Маппинг схем ответов по ролям
# ==============================================================================

RESPONSE_SCHEMAS: dict[UserRole, type[OrderResponseSchema]] = {
    UserRole.ADMIN: OrderResponseForAdmin,
    UserRole.SHOP: OrderResponseForShop,
    UserRole.COURIER: OrderResponseForCourier,
}

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
    "RESPONSE_SCHEMAS",
    "SECONDS_IN_MINUTE",
    "VALIDATION",
    "CommissionRules",
    "OrderResponseSchema",
    "PaginatedResponse",
    "RetrievePermissionCheck",
    "UpdatePayload",
    "UpdatePermissionCheck",
    "ValidationRules",
]
