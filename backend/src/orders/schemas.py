from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.src.common.enums import OrderStatus, OrderType, SpecialOrderType

PhoneFlexible = str


class OrderCreateRequest(BaseModel):
    """Схема для создания нового заказа магазином (входные данные API)."""

    description: str | None = Field(None, max_length=1000)
    recipient_address: str = Field(..., max_length=500)
    recipient_phone: PhoneFlexible
    delivery_time: datetime | None = None

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

        if self.order_type == OrderType.SPECIAL and self.courier_id is None:
            raise ValueError("Для специального заказа (special) необходимо указать courier_id")

        return self

    @model_validator(mode="after")
    def validate_delivery_time_logic(self) -> "OrderCreateRequest":
        """Валидация логики времени доставки для специальных заказов"""
        # Для заказов типа TIME время доставки обязательно
        if self.special_type == SpecialOrderType.TIME and self.delivery_time is None:
            raise ValueError("Для заказа типа TIME необходимо указать время доставки")

        # Опционально: проверить, что время доставки в будущем (если указано)
        if self.delivery_time is not None and self.delivery_time <= datetime.now(UTC):
            raise ValueError("Время доставки должно быть в будущем")

        return self


class OrderCreate(OrderCreateRequest):
    """Схема для создания нового заказа (внутреннее использование в сервисах)."""

    shop_id: int


class OrderUpdate(BaseModel):
    """Схема для обновления заказа."""

    status: OrderStatus | None = None
    courier_id: int | None = Field(None, description="ID курьера для назначения или изменения")
    courier_notes: str | None = Field(None, max_length=1000)
    completion_notes: str | None = Field(None, max_length=1000)

    model_config = ConfigDict(from_attributes=True)


class ShopInfoForCourier(BaseModel):
    """Информация о магазине для курьера."""

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class CourierInfoForShop(BaseModel):
    """Информация о курьере для магазина."""

    id: int
    name: str = Field(alias="full_name")

    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)


class OrderResponse(BaseModel):
    """Схема для полного представления заказа, включая все поля."""

    description: str | None = Field(None, max_length=1000)
    recipient_address: str
    recipient_phone: str
    delivery_time: datetime | None = None

    id: int
    status: OrderStatus
    order_type: OrderType
    special_type: SpecialOrderType | None = None

    client_phone: str
    photo_report_id: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderResponseForShop(OrderResponse):
    courier: CourierInfoForShop | None = None
    price: Decimal


class OrderResponseForCourier(OrderResponse):
    shop: ShopInfoForCourier


class OrderResponseForAdmin(OrderResponseForShop, OrderResponseForCourier): ...


class OrderCardResponse(BaseModel):
    """
    Схема для ответа с данными карточки заказа и кнопками на основе роли пользователя.
    """

    id: int
    shop_id: int | None
    shop_name: str | None
    courier_id: int | None
    courier_name: str | None
    status: OrderStatus
    order_type: OrderType
    special_type: SpecialOrderType | None = None
    price: Decimal
    recipient_address: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def flatten_names(cls, v: Any) -> Any:
        """Извлекает имена магазина и курьера из связанных объектов."""
        if not isinstance(v, dict):
            # Если это ORM объект, преобразуем его в dict с нужными полями
            shop_name = v.shop.name if v.shop else None
            courier_name = v.courier.full_name if v.courier else None

            return {
                "id": v.id,
                "shop_id": v.shop_id,
                "shop_name": shop_name,
                "courier_id": v.courier_id,
                "courier_name": courier_name,
                "status": v.status,
                "order_type": v.order_type,
                "special_type": v.special_type,
                "price": v.price,
                "recipient_address": v.recipient_address,
                "created_at": v.created_at,
            }
        return v


class OrderListFilters(BaseModel):
    """Фильтры для списка заказов."""

    page: int = Field(default=1, ge=1, description="Номер страницы")
    limit: int = Field(default=20, ge=1, le=100, description="Количество элементов на странице")
    status: OrderStatus | None = Field(None, description="Фильтр по статусу заказа")
    shop_id: int | None = Field(None, description="Фильтр по ID магазина (только для админа)")
    courier_id: int | None = Field(None, description="Фильтр по ID курьера (только для админа)")
    current: bool | None = Field(None, description="Только текущие (не завершённые) заказы")

    model_config = ConfigDict(from_attributes=True)


class OrderListItemForShop(BaseModel):
    """Краткая информация о заказе для магазина в списке."""

    id: int
    status: OrderStatus
    order_type: OrderType
    special_type: SpecialOrderType | None = None
    price: Decimal
    recipient_address: str
    delivery_time: datetime | None = None
    created_at: datetime
    courier: CourierInfoForShop | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderListItemForCourier(BaseModel):
    """Краткая информация о заказе для курьера в списке."""

    id: int
    status: OrderStatus
    order_type: OrderType
    special_type: SpecialOrderType | None = None
    recipient_address: str
    recipient_phone: str
    delivery_time: datetime | None = None
    created_at: datetime
    shop: ShopInfoForCourier

    model_config = ConfigDict(from_attributes=True)


class OrderListItemForAdmin(BaseModel):
    """Краткая информация о заказе для администратора в списке."""

    id: int
    status: OrderStatus
    order_type: OrderType
    special_type: SpecialOrderType | None = None
    price: Decimal
    recipient_address: str
    delivery_time: datetime | None = None
    created_at: datetime
    completed_at: datetime | None = None
    shop: ShopInfoForCourier
    courier: CourierInfoForShop | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderCompleteRequest(BaseModel):
    """Схема для завершения заказа с фото-отчетом."""

    photo_report_id: str = Field(..., max_length=255, description="ID фото-отчета в Telegram")

    model_config = ConfigDict(from_attributes=True)
