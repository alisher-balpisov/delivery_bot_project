from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.orders_client import OrdersClient
from bot.dto import UserDTO
from bot.filters.filters import RoleFilter
from bot.messages import CourierMessages

from . import service

logger = get_logger(__name__)
courier_router = Router(name="courier_handlers")


@courier_router.message(Command("available_orders"), RoleFilter(UserRole.COURIER))
async def available_orders_handler(message: Message, orders_client: OrdersClient):
    """Показать доступные заказы для курьеров."""
    telegram_id = message.from_user.id

    messages_to_send = await service.get_available_orders_messages(telegram_id, orders_client)

    if not messages_to_send:
        await message.answer(CourierMessages.NO_AVAILABLE_ORDERS)
        return

    for text, keyboard in messages_to_send:
        await message.answer(text, reply_markup=keyboard)


@courier_router.callback_query(F.data.startswith("take_order_"), RoleFilter(UserRole.COURIER))
async def take_order_handler(callback: CallbackQuery, user: UserDTO, orders_client: OrdersClient):
    """Обработка принятия заказа курьером."""
    try:
        order_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        logger.warning(f"Некорректный callback: {callback.data} от {callback.from_user.id}")
        await callback.answer(CourierMessages.INVALID_ORDER_ID_ERROR, show_alert=True)
        return

    response_text = await service.take_order(user, order_id, orders_client)

    await callback.message.edit_text(response_text)
    await callback.answer()
