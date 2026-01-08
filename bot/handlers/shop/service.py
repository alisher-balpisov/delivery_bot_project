from typing import Any

from aiogram.types import InlineKeyboardMarkup
from backend.src.core.logging import get_logger
from bot.clients.orders_client import OrdersClient
from bot.constants import OrderStatus
from bot.exceptions import ErrorMessages
from bot.keyboards.shops import get_order_confirmation_keyboard
from bot.messages import OrderMessages, ShopMessages

logger = get_logger(__name__)


def validate_price(price_text: str) -> tuple[float | None, str | None]:
    """Валидирует цену."""
    try:
        price = float(price_text.replace(",", "."))
        if price <= 0:
            return None, ErrorMessages.Orders.INVALID_PRICE
        return price, None
    except (ValueError, TypeError):
        return None, ErrorMessages.Orders.PRICE_FORMAT_ERROR


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
) -> str:
    """Отправляет запрос на создание заказа в API и возвращает текст с результатом."""
    if not token:
        return ErrorMessages.Auth.UNAUTHORIZED

    order_data = {
        "description": order_details.get("description"),
        "pickup_address": order_details.get("pickup_address"),
        "recipient_address": order_details.get("delivery_address"),
        "price": order_details.get("price"),
        "status": OrderStatus.CREATED.value,
        # TODO: Добавить другие обязательные поля, такие как recipient_phone, zone_id и т.д.
        "recipient_phone": "+70000000000",  # Заглушка
        "zone_id": 1,  # Заглушка
    }

    try:
        result = await orders_client.create_order(token, order_data)

        if result.success and isinstance(result.data, dict) and result.data.get("id"):
            return OrderMessages.SUCCESSFULLY_CREATED.format(result.data["id"])
        else:
            error_msg = result.detail or ShopMessages.UNKNOWN_ERROR
            return ErrorMessages.Orders.ORDER_CREATION_ERROR(error=error_msg)
    except Exception as e:
        logger.error(ShopMessages.CREATE_ORDER_CRITICAL_ERROR.format(e), exc_info=True)
        return ErrorMessages.Orders.ORDER_CREATION_ERROR(error=ShopMessages.UNKNOWN_ERROR)
