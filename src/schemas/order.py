from datetime import datetime

from pydantic import BaseModel, ConfigDict
from src.common.enums import OrderStatus, OrderType

from .shop import ShopRead


class CourierRating:
    """
    Рейтинг курьера от 1 до 5.
    """

    ge = 1
    le = 5


class OrderBase(BaseModel):
    """Базовая схема для заказа."""

    description: str | None = None
    recipient_name: str | None = None
    recipient_phone: str
    recipient_address: str
    price: float
    pickup_address: str
    delivery_time: datetime | None = None
    is_fragile: bool = False
    is_bulky: bool = False
    special_reason: str | None = None
    recipient_phone_code: str | None = None  # Optional field for phone code

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(OrderBase):
    """Схема для создания нового заказа магазином."""

    zone_id: int
    order_type: OrderType = OrderType.normal
    zone_addon: float = 0.0
    rush_hour_addon: float = 0.0


class OrderUpdate(BaseModel):
    """Схема для обновления заказа (например, курьером)."""

    status: OrderStatus | None = None
    courier_id: int | None = None
    courier_notes: str | None = None
    completion_notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderRead(OrderBase):
    """Схема для чтения данных заказа."""

    id: int
    order_type: OrderType
    zone_addon: float
    rush_hour_addon: float
    status: OrderStatus
    shop: ShopRead
    courier_id: int | None = None
    accepted_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(OrderBase):
    """Схема для ответа с данными заказа."""

    id: int
    shop_id: int
    zone_id: int
    courier_id: int | None = None
    status: OrderStatus
    order_type: OrderType
    zone_addon: float
    rush_hour_addon: float
    confirmed_at: datetime | None = None
    autoconfirmed_at: datetime | None = None
    accepted_at: datetime | None = None
    delivered_at: datetime | None = None
    courier_rating: int | None = None
    courier_feedback: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
