import re
from datetime import datetime

from backend.src.common.enums import OrderStatus, OrderType
from backend.src.common.utils import Phone
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .shop import ShopRead


class OrderBase(BaseModel):
    """Базовая схема для заказа."""

    description: str | None = None
    recipient_name: str | None = Field(None, max_length=100)
    recipient_phone: Phone
    recipient_address: str = Field(..., max_length=255)
    pickup_address: str = Field(..., max_length=255)
    delivery_time: datetime | None = None
    is_fragile: bool = False
    is_bulky: bool = False
    special_reason: str | None = Field(None, max_length=500)

    model_config = ConfigDict(from_attributes=True)

    @field_validator(
        "description",
        "recipient_name",
        "recipient_address",
        "pickup_address",
        "special_reason",
        mode="before",
    )
    @classmethod
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            v = re.sub(r"<[^>]*>", "", v)  # Remove HTML tags
        return v


class OrderCreateRequest(OrderBase):
    """Схема для создания нового заказа магазином (входные данные API)."""

    zone_id: int
    order_type: OrderType = OrderType.NORMAL
    zone_addon: float = 0.0
    rush_hour_addon: float = 0.0


class OrderCreate(OrderCreateRequest):
    """Схема для создания нового заказа (внутреннее использование в сервисах)."""

    shop_id: int  # Это поле добавляется сервером из данных токена


class OrderUpdate(BaseModel):
    """Схема для обновления заказа."""

    status: OrderStatus | None = None
    courier_notes: str | None = Field(None, max_length=1000)
    completion_notes: str | None = Field(None, max_length=1000)
    courier_rating: int | None = Field(None, ge=1, le=5)
    courier_feedback: str | None = Field(None, max_length=1000)

    model_config = ConfigDict(from_attributes=True)


class OrderRead(OrderBase):
    """Схема для чтения данных заказа (ответ API)."""

    id: int
    status: OrderStatus
    order_type: OrderType
    price: float
    shop: ShopRead  # Используем вложенную схему для данных о магазине
    courier_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(OrderBase):
    """Схема для полного представления заказа, включая все поля."""

    id: int
    shop_id: int
    zone_id: int
    courier_id: int | None = None
    status: OrderStatus
    order_type: OrderType
    price: float
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
