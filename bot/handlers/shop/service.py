from typing import Any

from aiogram.types import InlineKeyboardMarkup
from backend.src.common.enums import OrderStatus
from backend.src.core.logging import get_logger
from bot.clients import client_manager
from bot.constants import ErrorMessages
from bot.handlers.keyboards import get_order_confirmation_keyboard
from bot.messages import OrderMessages, ShopMessages

logger = get_logger(__name__)


def validate_price(price_text: str) -> tuple[float | None, str | None]:
    """
    Валидирует цену.
    Возвращает (цена, None) при успехе или (None, сообщение_об_ошибке) при неудаче.
    """
    try:
        price = float(price_text)
        if price <= 0:
            return None, ErrorMessages.Orders.INVALID_PRICE
        return price, None
    except ValueError:
        return None, ErrorMessages.Orders.PRICE_FORMAT_ERROR


def format_order_confirmation(data: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует текст и клавиатуру для подтверждения заказа.
    """
    text = OrderMessages.CONFIRMATION_PROMPT.format(
        description=data.get("description", "N/A"),
        pickup_address=data.get("pickup_address", "N/A"),
        delivery_address=data.get("delivery_address", "N/A"),
        price=data.get("price", 0),
    )

    keyboard = get_order_confirmation_keyboard()
    return text, keyboard


async def create_order(telegram_id: int, order_details: dict[str, Any]) -> str:
    """
    Отправляет запрос на создание заказа в API и возвращает текст с результатом.
    """
    order_data = {
        "description": order_details.get("description"),
        "pickup_address": order_details.get("pickup_address"),
        "delivery_address": order_details.get("delivery_address"),
        "price": order_details.get("price"),
        "status": OrderStatus.CREATED,
    }

    try:
        result = await client_manager.orders.create_order(telegram_id, order_data)
        if result and result.get("id"):
            return OrderMessages.SUCCESSFULLY_CREATED.format(result["id"])
        else:
            error_msg = (
                result.get("detail", ShopMessages.UNKNOWN_ERROR)
                if result
                else ShopMessages.SERVER_ERROR
            )
            return ErrorMessages.Orders.order_creation_error(error=error_msg)
    except Exception as e:
        logger.error(ShopMessages.CREATE_ORDER_CRITICAL_ERROR.format(telegram_id, e), exc_info=True)
        return ErrorMessages.Orders.order_creation_error(error=ShopMessages.INTERNAL_ERROR)
