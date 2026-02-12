"""Обработчик ввода описания заказа."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import DeliveryTimeType, OrderType, UserRole

from bot.filters.filters import RoleFilter
from bot.handlers.shop.formatters.order import format_order_preview
from bot.handlers.shop.keyboards.create_order import get_order_settings_keyboard
from bot.handlers.shop.keyboards.main import get_back_to_menu_keyboard
from bot.handlers.shop.messages import OrderCreateMessages
from bot.handlers.shop.states import OrderCreateStates
from bot.redis_storage import UserDataStorage

router = Router(name="order_create_description")


@router.callback_query(F.data == "create_order", RoleFilter(UserRole.SHOP))
async def start_order_creation(callback: CallbackQuery, state: FSMContext):
    """Начало создания заказа."""
    await state.clear()

    keyboard = get_back_to_menu_keyboard()

    await callback.message.edit_text(
        OrderCreateMessages.DESCRIPTION_PROMPT, reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(OrderCreateStates.waiting_for_description)
    await callback.answer()


@router.message(OrderCreateStates.waiting_for_description, RoleFilter(UserRole.SHOP))
async def process_description(
    message: Message,
    state: FSMContext,
    user_storage: UserDataStorage,
):
    """Обработка описания заказа."""
    description = message.text

    if not description:
        await message.answer(
            "⚠️ Пожалуйста, введите <b>текстовое</b> описание заказа.", parse_mode="HTML"
        )
        return

    # Сохраняем описание
    await state.update_data(description=description)

    # Устанавливаем дефолтные значения
    order_type = OrderType.REGULAR.value
    delivery_time_type = DeliveryTimeType.TODAY.value
    await state.update_data(order_type=order_type, delivery_time_type=delivery_time_type)

    # Формируем предпросмотр
    data = await state.get_data()
    text = format_order_preview(
        description=description,
        order_type=order_type,
        price=data.get("price"),
    )

    # Отправляем предпросмотр
    await message.answer(
        text=text,
        reply_markup=get_order_settings_keyboard(
            order_type=order_type,
            delivery_time_type=DeliveryTimeType.TODAY,
            price=data.get("price"),
        ),
        parse_mode="HTML",
    )
