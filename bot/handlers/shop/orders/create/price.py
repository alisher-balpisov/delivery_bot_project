"""Обработчики установки цены заказа."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import OrderType, UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.couriers_client import CouriersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.formatters.order import format_order_confirmation
from bot.handlers.shop.keyboards.create_order import (
    get_confirmation_keyboard,
    get_price_input_keyboard,
)
from bot.handlers.shop.messages import OrderCreateMessages
from bot.handlers.shop.states import OrderCreateStates
from bot.handlers.shop.validators.price import validate_price
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

router = Router(name="order_create_price")


@router.callback_query(F.data == "set_order_price", RoleFilter(UserRole.SHOP))
async def request_price(callback: CallbackQuery, state: FSMContext):
    """Запросить ввод цены."""
    data = await state.get_data()

    if not data.get("description"):
        await callback.answer("⚠️ Сначала введите описание заказа", show_alert=True)
        return

    # Проверка требований для TIME
    order_type = data.get("order_type")
    if order_type == OrderType.TIME.value:
        from backend.src.common.enums import DeliveryTimeType

        delivery_time_type = data.get("delivery_time_type")
        if delivery_time_type == DeliveryTimeType.SCHEDULED.value and not data.get("delivery_time"):
            await callback.answer(
                "⚠️ Для заказа 'Ко времени' нужно указать время доставки", show_alert=True
            )
            return

    await callback.message.edit_text(
        text=OrderCreateMessages.PRICE_PROMPT,
        reply_markup=get_price_input_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderCreateStates.waiting_for_price)
    await callback.answer()


@router.message(OrderCreateStates.waiting_for_price, RoleFilter(UserRole.SHOP))
@router.message(OrderCreateStates.editing_price, RoleFilter(UserRole.SHOP))
async def process_price_input(
    message: Message,
    state: FSMContext,
    couriers_client: CouriersClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Обработать ввод цены."""
    price_text = message.text
    data = await state.get_data()
    is_editing = data.get("is_editing", False)
    back_callback = "edit_order_menu" if is_editing else "back_to_preview"

    if not price_text:
        await message.answer("⚠️ Пожалуйста, введите цену числом.", parse_mode="HTML")
        return

    # Валидация
    price, error = validate_price(price_text)

    if error:
        await message.answer(
            f"❌ {error}\n\n<i>Введите цену от 3 000 до 20 000 ₸</i>",
            reply_markup=get_price_input_keyboard(back_callback=back_callback),
            parse_mode="HTML",
        )
        return

    # Сохраняем цену
    await state.update_data(price=price, is_editing=False)
    data = await state.get_data()

    # В режиме редактирования - сразу к подтверждению
    if is_editing:
        await _proceed_to_confirmation(message, state)
        return

    # Для REGULAR - пропускаем выбор курьера
    order_type = data.get("order_type", OrderType.REGULAR.value)
    if order_type == OrderType.REGULAR.value:
        await _proceed_to_confirmation(message, state)
        return

    # Для других типов - выбор курьера
    from bot.handlers.shop.orders.create.courier import request_courier_selection

    telegram_id = message.from_user.id
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(telegram_id)

    if not token:
        await message.answer("⚠️ Ошибка авторизации. Попробуйте начать заново.")
        return

    await request_courier_selection(message, state, token, couriers_client, page=1)


@router.callback_query(F.data == "skip_price", RoleFilter(UserRole.SHOP))
async def skip_price(
    callback: CallbackQuery,
    state: FSMContext,
    couriers_client: CouriersClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Пропустить установку цены."""
    data = await state.get_data()
    is_editing = data.get("is_editing", False)

    await state.update_data(price=None, is_editing=False)
    data = await state.get_data()

    # В режиме редактирования - к подтверждению
    if is_editing:
        await _proceed_to_confirmation(callback.message, state)
        await callback.answer()
        return

    # Для REGULAR - к подтверждению
    order_type = data.get("order_type", OrderType.REGULAR.value)
    if order_type == OrderType.REGULAR.value:
        await _proceed_to_confirmation(callback.message, state)
        await callback.answer()
        return

    # Для других типов - выбор курьера
    from bot.handlers.shop.orders.create.courier import request_courier_selection

    telegram_id = callback.from_user.id
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(telegram_id)

    if not token:
        await callback.message.answer("⚠️ Ошибка авторизации. Попробуйте начать заново.")
        return

    await request_courier_selection(callback.message, state, token, couriers_client, page=1)
    await callback.answer()


async def _proceed_to_confirmation(message: Message, state: FSMContext):
    """Переход к подтверждению заказа."""
    data = await state.get_data()

    text = format_order_confirmation(
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=data.get("price"),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await message.answer(
        text=text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderCreateStates.confirmation)
