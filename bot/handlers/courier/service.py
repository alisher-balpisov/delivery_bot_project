from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from backend.src.common.enums import OrderStatus
from backend.src.core.logging import get_logger
from bot.clients import client_manager
from bot.constants import ErrorMessages
from bot.messages import CourierMessages, OrderMessages

logger = get_logger(__name__)


async def get_available_orders_messages(
    telegram_id: int,
) -> list[tuple[str, InlineKeyboardMarkup]]:
    """
    Получает доступные заказы и форматирует их в список кортежей (текст, клавиатура).
    Возвращает пустой список, если заказов нет.
    """
    try:
        orders = await client_manager.orders.get_available_orders(telegram_id)
        if not orders:
            return []

        messages = []
        # Показываем не более 5 заказов
        for order in orders[:5]:
            order_id = order.get("id")
            text = OrderMessages.AVAILABLE_ORDER_TEMPLATE.format(
                order_id=order_id,
                pickup_address=order.get("pickup_address"),
                delivery_address=order.get("delivery_address"),
                price=order.get("price"),
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=CourierMessages.ACCEPT_ORDER,
                            callback_data=f"take_order_{order_id}",
                        )
                    ]
                ]
            )
            messages.append((text, keyboard))
        return messages
    except Exception as e:
        logger.error(CourierMessages.AVAILABLE_ORDERS_ERROR.format(telegram_id, e), exc_info=True)
        return []  # В случае ошибки возвращаем пустой список, чтобы хендлер мог корректно отработать


async def take_order(telegram_id: int, user_id: int | None, order_id: int) -> str:
    """
    Обрабатывает принятие заказа курьером.
    Возвращает строку с результатом операции для отправки пользователю.
    """
    if not user_id:
        logger.error(CourierMessages.MISSING_USER_ID.format(telegram_id))
        return ErrorMessages.UserData.USER_DATA_ERROR

    payload = {"status": OrderStatus.ACCEPTED, "courier_id": user_id}

    try:
        result = await client_manager.orders.update_order_status(telegram_id, order_id, payload)
        if result and result.get("success") is not False:
            return OrderMessages.ORDER_ACCEPTED.format(order_id)
        else:
            error_msg = (
                result.get("detail", CourierMessages.ORDER_ALREADY_TAKEN)
                if result
                else CourierMessages.SERVER_ERROR
            )
            return ErrorMessages.Orders.order_accept_error(error=error_msg)
    except Exception as e:
        logger.error(
            CourierMessages.TAKE_ORDER_CRITICAL_ERROR.format(order_id, telegram_id, e),
            exc_info=True,
        )
        return ErrorMessages.Orders.order_accept_error(error=CourierMessages.INTERNAL_ERROR)
