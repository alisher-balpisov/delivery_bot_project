"""Форматтеры для заказов."""

import html
from datetime import datetime

from backend.src.common.enums import DeliveryTimeType, OrderType


def format_order_preview(
    description: str,
    order_type: str,
    delivery_time: datetime | None = None,
    delivery_time_type: str | None = None,
    price: int | None = None,
) -> str:
    """Форматирует предпросмотр заказа перед созданием."""
    order_type_labels = {
        OrderType.REGULAR.value: "🚴 Обычный",
        OrderType.TIME.value: "⏰ Ко времени",
        OrderType.DISTANCE.value: "🗺️ Дальний",
        OrderType.CUSTOM.value: "📦 Особый",
        OrderType.SUPPLY.value: "🏭 Со склада",
    }
    order_type_display = order_type_labels.get(order_type, order_type)

    # Экранируем данные
    description = html.escape(description)

    text = (
        "<b>📋 Предпросмотр заказа</b>\n\n"
        f"📝 <b>Детали заказа:</b>\n{description}\n\n"
        f"📦 <b>Тип заказа:</b> {order_type_display}\n"
    )

    # Информация о времени для типа TIME
    if order_type == OrderType.TIME.value:
        time_labels = {
            DeliveryTimeType.ASAP.value: "🚀 Как можно скорее",
            DeliveryTimeType.TODAY.value: "📅 В течение дня",
            DeliveryTimeType.SCHEDULED.value: "⏰ К конкретному времени",
        }
        time_display = time_labels.get(delivery_time_type, "Не указано")
        text += f"⏱️ <b>Срочность:</b> {time_display}\n"

        if delivery_time and delivery_time_type == DeliveryTimeType.SCHEDULED.value:
            text += f"🕐 <b>Время:</b> {delivery_time.strftime('%d.%m.%Y %H:%M')}\n"

    # Цена
    if price is not None:
        text += f"\n💰 <b>Цена доставки:</b> {price:,} ₸\n"
    else:
        text += "\n💰 <b>Цена доставки:</b> <i>Не указана</i>\n"

    text += "\n<i>Настройте параметры заказа используя кнопки ниже.</i>"

    return text


def format_order_confirmation(
    description: str,
    order_type: str,
    price: int | None = None,
    delivery_time: datetime | None = None,
    delivery_time_type: str | None = None,
    courier_name: str | None = None,
) -> str:
    """Форматирует финальное подтверждение заказа."""
    order_type_labels = {
        OrderType.REGULAR.value: "🚴 Обычный",
        OrderType.TIME.value: "⏰ Ко времени",
        OrderType.DISTANCE.value: "🗺️ Дальний",
        OrderType.CUSTOM.value: "📦 Особый",
        OrderType.SUPPLY.value: "🏭 Со склада",
    }
    order_type_display = order_type_labels.get(order_type, order_type)

    # Экранируем данные
    description = html.escape(description)
    if courier_name:
        courier_name = html.escape(courier_name)

    price_str = f"{price:,} ₸" if price is not None else "<i>Не указана</i>"

    text = (
        "<b>✅ Подтверждение заказа</b>\n"
        f"📝 <b>Описание:</b>\n{description}\n\n"
        f"📦 <b>Тип:</b> {order_type_display}\n"
        f"💰 <b>Цена:</b> {price_str}\n"
    )

    if order_type == OrderType.TIME.value and delivery_time:
        text += f"🕐 <b>Время доставки:</b> {delivery_time.strftime('%d.%m.%Y %H:%M')}\n"

    if courier_name:
        text += f"🚚 <b>Курьер:</b> {courier_name}\n"
    elif order_type != OrderType.REGULAR.value:
        text += "🚚 <b>Курьер:</b> Автоматический подбор\n"

    text += "\n\n<b>Подтвердите создание заказа</b>"

    return text
