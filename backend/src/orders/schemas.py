from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.src.common.constants import MAX_ALLOWED_DATE_FOR_ORDER
from backend.src.common.enums import DeliveryTimeType, OrderStatus, OrderType

PhoneFlexible = str


class OrderCreateRequest(BaseModel):
    """Схема для создания нового заказа магазином (входные данные API)."""

    courier_id: int | None = Field(None, description="ID курьера (для специальных типов заказов)")
    delivery_time: datetime | None = None
    delivery_time_type: DeliveryTimeType = Field(DeliveryTimeType.TODAY)
    order_type: OrderType = Field(OrderType.REGULAR, description="Тип заказа")
    price: Decimal = Field(
        ...,
        ge=3000,
        le=20000,
        multiple_of=1,
        description="Цена доставки, устанавливаемая магазином",
    )
    description: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def validate_delivery_type_consistency(self) -> "OrderCreateRequest":
        # Если заказали "Как можно скорее" (ASAP), конкретное время обычно не указывают
        if self.delivery_time_type == DeliveryTimeType.ASAP and self.delivery_time is not None:
            # Либо ошибка, либо ворнинг, либо зануление
            # raise ValueError("При выборе ASAP нельзя указывать конкретное время доставки")
            self.delivery_time = None  # Или просто очищаем лишнее

        return self

    @model_validator(mode="after")
    def validate_max_future_date(self):
        """
        Проверка горизота планирования.
        """
        if self.delivery_time:
            now_utc = datetime.now(UTC)

            # Приводим delivery_time к UTC для корректного сравнения
            check_time = self.delivery_time
            if check_time.tzinfo is None:
                check_time = check_time.replace(tzinfo=UTC)

            max_allowed_date = now_utc + timedelta(days=MAX_ALLOWED_DATE_FOR_ORDER)
            if check_time > max_allowed_date:
                raise ValueError(
                    f"Нельзя планировать доставку более чем на {MAX_ALLOWED_DATE_FOR_ORDER} дней вперед"
                )
        return self

    @model_validator(mode="after")
    def validate_order_logic(self):
        """
        Комплексная валидация логики заказа.
        """
        # --- 1. Валидация связки OrderType и Courier ---
        if self.order_type == OrderType.REGULAR:
            if self.courier_id is not None:
                raise ValueError(
                    "Для обычного заказа (regular) нельзя указывать courier_id. Он назначается системой."
                )
        else:
            if self.courier_id is None:
                raise ValueError(
                    f"Для заказа типа {self.order_type.value} необходимо указать courier_id."
                )

        # --- 2. Валидация времени доставки ---
        if self.order_type == OrderType.TIME and self.delivery_time is None:
            raise ValueError("Для заказа типа TIME необходимо указать поле delivery_time.")

        if self.delivery_time is not None:
            now_utc = datetime.now(UTC)
            input_time = self.delivery_time

            # Обработка таймзоны
            if input_time.tzinfo is None:
                input_time = input_time.replace(tzinfo=UTC)

            if input_time <= now_utc:
                raise ValueError(
                    f"Время доставки должно быть в будущем. (Сейчас: {now_utc.strftime('%H:%M')})"
                )

        return self


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
