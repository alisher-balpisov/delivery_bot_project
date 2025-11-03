import re
from datetime import datetime
from decimal import Decimal

from backend.src.common.enums import OrderStatus, OrderType, SpecialOrderType
from backend.src.common.utils import PhoneFlexible
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OrderBase(BaseModel):
    """Базовая схема для заказа."""

    description: str | None = Field(None, max_length=1000)
    recipient_address: str = Field(..., max_length=500)
    recipient_phone: PhoneFlexible
    delivery_time: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("description", "recipient_address", mode="before")
    @classmethod
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            v = re.sub(r"<[^>]*>", "", v)  # Remove HTML tags
        return v


class OrderCreateRequest(OrderBase):
    """Схема для создания нового заказа магазином (входные данные API)."""

    courier_id: int | None = Field(None, description="ID курьера (только для special заказов)")
    order_type: OrderType = Field(OrderType.REGULAR, description="Тип заказа: regular или special")
    special_type: SpecialOrderType | None = Field(
        None, description="Тип специального заказа (только если order_type=special)"
    )
    price: Decimal = Field(..., gt=0, description="Цена доставки, устанавливаемая магазином")
    client_phone: PhoneFlexible = Field(..., description="Телефон клиента")

    @model_validator(mode="after")
    def validate_order_type_logic(self):
        """Валидация логики типов заказов"""
        # Проверка: если order_type == regular, то special_type должен быть None
        if self.order_type == OrderType.REGULAR and self.special_type is not None:
            raise ValueError("Для обычного заказа (regular) special_type должен быть None")

        # Проверка: если order_type == special, то special_type должен быть указан
        if self.order_type == OrderType.SPECIAL and self.special_type is None:
            raise ValueError("Для специального заказа (special) необходимо указать special_type")

        # Проверка: courier_id должен быть указан только для special заказов
        if self.order_type == OrderType.REGULAR and self.courier_id is not None:
            raise ValueError("Для обычного заказа (regular) нельзя указывать courier_id")

        return self


class OrderCreate(OrderCreateRequest):
    """Схема для создания нового заказа (внутреннее использование в сервисах)."""

    shop_id: int  # Это поле добавляется сервером из данных токена


class OrderUpdate(BaseModel):
    """Схема для обновления заказа."""

    status: OrderStatus | None = None
    courier_notes: str | None = Field(None, max_length=1000)
    completion_notes: str | None = Field(None, max_length=1000)

    model_config = ConfigDict(from_attributes=True)


class OrderRead(OrderBase):
    """Схема для чтения данных заказа (ответ API)."""

    id: int
    shop_id: int
    courier_id: int | None = None
    status: OrderStatus
    order_type: OrderType
    special_type: SpecialOrderType | None = None
    price: Decimal
    client_phone: str
    photo_report_id: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(OrderBase):
    """Схема для полного представления заказа, включая все поля."""

    id: int
    shop_id: int
    courier_id: int | None = None
    status: OrderStatus
    order_type: OrderType
    special_type: SpecialOrderType | None = None
    price: Decimal
    client_phone: str
    photo_report_id: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderCardResponse(BaseModel):
    """Схема для отображения заказа в списке (карточка заказа для админа)."""

    id: int
    shop_id: int
    shop_name: str | None = None
    courier_id: int | None = None
    courier_name: str | None = None
    status: OrderStatus
    order_type: OrderType
    special_type: SpecialOrderType | None = None
    price: Decimal
    recipient_address: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
