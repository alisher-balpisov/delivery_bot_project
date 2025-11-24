from collections.abc import Awaitable, Callable
from typing import Any, Literal

from backend.src.auth.dependencies import User
from backend.src.common.enums import OrderStatus, UserRole
from backend.src.models.order import Order
from backend.src.orders.schemas import (
    OrderResponseForAdmin,
    OrderResponseForCourier,
    OrderResponseForShop,
)
from pydantic import BaseModel, Field

VALIDATION = {
    "min_order_price": 100,  # минимальная цена заказа в тенге
    "max_order_price": 1000000,  # максимальная цена заказа
    "max_description_length": 500,
    "max_address_length": 200,
    "dispute_time_limit": 86400,  # 24 часа для открытия спора
}

# Комиссии и платежи
COMMISSION: dict[str, Any] = {
    "platform_fee_percent": 10,  # комиссия платформы в процентах
    "min_commission": 50,  # минимальная комиссия в тенге
    "payment_methods": ["cash", "card", "kaspi"],
}


MIN_TELEGRAM_ID = 1
MAX_TELEGRAM_ID = 2147483647
SECONDS_IN_MINUTE = 60


type OrderResponseSchema = OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier

type UpdatePayload = dict[str, Any]

UpdatePermissionCheck = Callable[[User, Order, UpdatePayload], Awaitable[None]]
RetrievePermissionCheck = Callable[[User, Order], Awaitable[None]]


COURIER_ALLOWED_FIELDS = {"status", "courier_notes", "completion_notes"}

FINAL_STATUSES = {OrderStatus.COMPLETED, OrderStatus.CANCELED}


RESPONSE_SCHEMAS: dict[UserRole, type[OrderResponseSchema]] = {
    UserRole.ADMIN: OrderResponseForAdmin,
    UserRole.SHOP: OrderResponseForShop,
    UserRole.COURIER: OrderResponseForCourier,
}


class PaginatedResponse[T](BaseModel):
    total: int = Field(..., description="Общее количество элементов")
    items: list[T] = Field(..., description="Список элементов на текущей странице")
