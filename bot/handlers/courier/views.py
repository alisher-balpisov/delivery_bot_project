from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.filters import RoleFilter
from bot.messages import CourierMessages

from . import service

logger = get_logger(__name__)
courier_router = Router(name="courier_handlers")


@courier_router.message(Command("available_orders"), RoleFilter([UserRole.COURIER]))
async def available_orders_handler(message: Message):
    """Показать доступные заказы для курьеров."""
    telegram_id = message.from_user.id

    # Сервис возвращает готовый список сообщений для отправки
    messages_to_send = await service.get_available_orders_messages(telegram_id)

    if not messages_to_send:
        await message.answer(CourierMessages.NO_AVAILABLE_ORDERS)
        return

    for text, keyboard in messages_to_send:
        await message.answer(text, reply_markup=keyboard)


@courier_router.callback_query(F.data.startswith("take_order_"), RoleFilter([UserRole.COURIER]))
async def take_order_handler(callback: CallbackQuery, user_data: dict):
    """Обработка принятия заказа курьером."""
    try:
        order_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        logger.warning(f"Некорректный callback: {callback.data} от {callback.from_user.id}")
        await callback.answer(CourierMessages.INVALID_ORDER_ID_ERROR, show_alert=True)
        return

    telegram_id = callback.from_user.id
    user_id = user_data.get("user_id")

    # Сервис выполняет всю логику и возвращает готовый текст для ответа
    response_text = await service.take_order(telegram_id, user_id, order_id)

    await callback.message.edit_text(response_text)
    await callback.answer()
