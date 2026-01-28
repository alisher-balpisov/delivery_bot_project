from datetime import datetime
from decimal import Decimal
from typing import Any

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from backend.src.common.enums import DeliveryTimeType, OrderType
from backend.src.core.logging import get_logger

from bot.clients.orders_client import OrdersClient
from bot.exceptions import ErrorMessages
from bot.keyboards.shops import get_order_confirmation_keyboard
from bot.messages import OrderMessages, ShopMessages

logger = get_logger(__name__)


class OrderTypeCallback(CallbackData, prefix="set_ord_type"):
    """Callback для выбора типа заказа"""

    type: str  # Значение OrderType (regular, time и т.д.)


class DeliveryTimeTypeCallback(CallbackData, prefix="set_del_time"):
    """Callback для выбора типа времени доставки"""

    time_type: str  # Значение DeliveryTimeType (ASAP, TODAY, SCHEDULED)


# Константы для валидации цены
MIN_ORDER_PRICE = 3000
MAX_ORDER_PRICE = 20000


def validate_price(price_text: str) -> tuple[Decimal | None, str | None]:
    """
    Валидирует цену заказа.

    Args:
        price_text: Текст с ценой от пользователя

    Returns:
        Tuple(цена в Decimal или None, сообщение об ошибке или None)
    """
    try:
        # Очищаем текст от пробелов и заменяем запятую на точку
        cleaned = price_text.strip().replace(",", ".").replace(" ", "")
        price = Decimal(cleaned)

        if price < MIN_ORDER_PRICE:
            return None, f"Минимальная цена заказа: {MIN_ORDER_PRICE:,} ₸"
        if price > MAX_ORDER_PRICE:
            return None, f"Максимальная цена заказа: {MAX_ORDER_PRICE:,} ₸"

        return price, None

    except (ValueError, TypeError):
        return None, ErrorMessages.Orders.PRICE_FORMAT_ERROR


def validate_delivery_time(time_text: str) -> tuple[datetime | None, str | None]:
    """
    Валидирует время доставки.

    Поддерживаемые форматы:
    - HH:MM (сегодня в указанное время)
    - DD.MM HH:MM
    - DD.MM.YYYY HH:MM

    Args:
        time_text: Текст с временем от пользователя

    Returns:
        Tuple(datetime или None, сообщение об ошибке или None)
    """
    from datetime import timedelta

    now = datetime.now()
    time_text = time_text.strip()

    formats = [
        ("%H:%M", lambda dt: dt.replace(year=now.year, month=now.month, day=now.day)),
        ("%d.%m %H:%M", lambda dt: dt.replace(year=now.year)),
        ("%d.%m.%Y %H:%M", lambda dt: dt),
    ]

    for fmt, adjuster in formats:
        try:
            parsed = datetime.strptime(time_text, fmt)
            delivery_time = adjuster(parsed)

            # Проверяем, что время в будущем
            if delivery_time <= now:
                # Если указано только время и оно уже прошло - добавляем день
                if fmt == "%H:%M":
                    delivery_time += timedelta(days=1)
                else:
                    return None, "Время доставки должно быть в будущем"

            # Проверяем максимальный горизонт планирования (7 дней)
            max_date = now + timedelta(days=7)
            if delivery_time > max_date:
                return None, "Нельзя планировать доставку более чем на 7 дней вперёд"

            return delivery_time, None

        except ValueError:
            continue

    return None, (
        "Неверный формат времени. Используйте:\n"
        "• <code>HH:MM</code> - сегодня в указанное время\n"
        "• <code>ДД.ММ HH:MM</code> - конкретная дата и время\n"
        "• <code>ДД.ММ.ГГГГ HH:MM</code> - полная дата и время"
    )


def format_order_confirmation(data: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    """Форматирует текст и клавиатуру для подтверждения заказа."""
    text = OrderMessages.CONFIRMATION_PROMPT.format(
        description=data.get("description", "N/A"),
        pickup_address=data.get("pickup_address", "N/A"),
        delivery_address=data.get("delivery_address", "N/A"),
        price=data.get("price", 0),
    )
    keyboard = get_order_confirmation_keyboard()
    return text, keyboard


async def create_order(
    token: str | None,
    order_details: dict[str, Any],
    orders_client: OrdersClient,
) -> tuple[bool, str]:
    """
    Отправляет запрос на создание заказа в API.

    Args:
        token: Токен авторизации
        order_details: Данные заказа из FSM
        orders_client: Клиент API заказов

    Returns:
        Tuple(успех, сообщение, ID заказа или None)
    """
    if not token:
        return False, ErrorMessages.Auth.UNAUTHORIZED

    # Формируем данные для API
    order_data = {
        "description": order_details.get("description"),
        "price": float(order_details.get("price", 0)),
        "order_type": order_details.get("order_type", OrderType.REGULAR.value),
        "delivery_time_type": order_details.get("delivery_time_type", DeliveryTimeType.TODAY.value),
    }

    # Добавляем время доставки если указано
    delivery_time = order_details.get("delivery_time")
    if delivery_time:
        if isinstance(delivery_time, datetime):
            order_data["delivery_time"] = delivery_time.isoformat()
        else:
            order_data["delivery_time"] = delivery_time

    # Для не-REGULAR типов требуется указать courier_id (будет добавлено позже)
    order_type = order_details.get("order_type")
    if order_type and order_type != OrderType.REGULAR.value:
        courier_id = order_details.get("courier_id")
        if courier_id:
            order_data["courier_id"] = courier_id

    try:
        logger.info(f"Создание заказа: {order_data}")
        result = await orders_client.create_order(token, order_data)

        if result.success and isinstance(result.data, dict) and result.data.get("id"):
            order_id = result.data["id"]
            courier_id = result.data["courier_id"]
            courier_full_name: str = result.data["courier_full_name"]

            if not courier_id:
                return (True, OrderMessages.SUCCESSFULLY_CREATED_NO_COURIER.format(order_id))
            return (
                True,
                OrderMessages.SUCCESSFULLY_CREATED.format(
                    order_id=order_id, courier_name=courier_full_name.split()[1]
                ),
            )
        else:
            error_msg = result.detail or ShopMessages.UNKNOWN_ERROR
            return False, ErrorMessages.Orders.ORDER_CREATION_ERROR(error=error_msg)

    except Exception as e:
        logger.error(f"Критическая ошибка при создании заказа: {e}", exc_info=True)
        return (False, ErrorMessages.Orders.ORDER_CREATION_ERROR(error=ShopMessages.UNKNOWN_ERROR))


def get_order_type_requirements(order_type: str) -> dict[str, Any]:
    """
    Возвращает требования для указанного типа заказа.

    Args:
        order_type: Значение OrderType

    Returns:
        Словарь с требованиями (needs_courier, needs_time, description)
    """
    requirements = {
        OrderType.REGULAR.value: {
            "needs_courier": False,
            "needs_time": False,
            "description": "Обычный заказ. Курьер назначается автоматически.",
        },
        OrderType.TIME.value: {
            "needs_courier": True,
            "needs_time": True,
            "description": "Доставка к определённому времени. Требуется указать время и курьера.",
        },
        OrderType.DISTANCE.value: {
            "needs_courier": True,
            "needs_time": False,
            "description": "Дальняя доставка. Требуется выбрать курьера.",
        },
        OrderType.CUSTOM.value: {
            "needs_courier": True,
            "needs_time": False,
            "description": "Особый заказ (габаритный груз). Требуется выбрать курьера.",
        },
        OrderType.SUPPLY.value: {
            "needs_courier": True,
            "needs_time": False,
            "description": "Доставка со склада. Требуется выбрать курьера.",
        },
    }

    return requirements.get(order_type, requirements[OrderType.REGULAR.value])
