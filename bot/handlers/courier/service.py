from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from backend.src.common.enums import OrderStatus
from backend.src.core.logging import get_logger
from bot.clients.orders_client import OrdersClient
from bot.dto import UserDTO
from bot.exceptions import ErrorMessages
from bot.messages import CourierMessages, OrderMessages, ShopMessages

logger = get_logger(__name__)


async def get_available_orders_messages(
    token: str | None,
    orders_client: OrdersClient,
) -> list[tuple[str, InlineKeyboardMarkup]]:
    """
    Получает доступные заказы и форматирует их в список кортежей (текст, клавиатура).
    """
    if not token:
        # Return an empty list, the handler will inform the user.
        return []

    try:
        result = await orders_client.get_available_orders(token)
        if not result.success or not isinstance(result.data, list):
            logger.error(f"Ошибка получения доступных заказов: {result.detail}")
            return []

        orders = result.data
        if not orders:
            return []

        messages = []
        for order in orders[:5]:
            order_id = order.get("id")
            if not order_id:
                continue

            text = OrderMessages.AVAILABLE_ORDER_TEMPLATE.format(
                order_id=order_id,
                pickup_address=order.get("pickup_address", "N/A"),
                recipient_address=order.get("recipient_address", "N/A"),
                price=order.get("price", "N/A"),
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
        logger.error(CourierMessages.AVAILABLE_ORDERS_ERROR.format(e), exc_info=True)
        return []


async def take_order(
    token: str | None,
    user: UserDTO,
    order_id: int,
    orders_client: OrdersClient,
) -> str:
    """
    Обрабатывает принятие заказа курьером.
    """
    if not token:
        return ErrorMessages.Auth.UNAUTHORIZED
    if not user.user_id:
        logger.error(CourierMessages.MISSING_USER_ID.format(user.telegram_id))
        return ErrorMessages.UserData.USER_DATA_ERROR

    payload = {"status": OrderStatus.ACCEPTED.value}

    try:
        result = await orders_client.update_order_status(token, order_id, payload)

        if result.success:
            return OrderMessages.ORDER_ACCEPTED.format(order_id)
        else:
            error_msg = result.detail or CourierMessages.ORDER_ALREADY_TAKEN
            return ErrorMessages.Orders.ORDER_ACCEPT_ERROR(error=error_msg)
    except Exception as e:
        logger.error(
            CourierMessages.TAKE_ORDER_CRITICAL_ERROR.format(order_id, user.telegram_id, e),
            exc_info=True,
        )
        return ErrorMessages.Orders.ORDER_ACCEPT_ERROR(error=ShopMessages.UNKNOWN_ERROR)
