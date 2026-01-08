# handlers_orders.py — Создание заказа (FSM), история (для магазина)
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.messages import OrderMessages
from bot.redis_storage import UserDataStorage
from bot.states import OrderStates
from bot.utils.token_manager import TokenManager

from . import service

router = Router(name="shop_orders_handlers")


@router.message(Command("new_order"), RoleFilter(UserRole.SHOP))
async def new_order_handler(message: Message, state: FSMContext):
    """Начать создание нового заказа."""
    await state.set_state(OrderStates.waiting_for_description)
    await message.answer(OrderMessages.STEP_1_DESCRIPTION)


@router.callback_query(F.data == "create_order", RoleFilter(UserRole.SHOP))
async def create_order_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Начать создание нового заказа (через inline-кнопку)."""
    await state.set_state(OrderStates.waiting_for_description)
    await callback.message.answer(OrderMessages.STEP_1_DESCRIPTION)
    await callback.answer()


@router.callback_query(F.data == "show_current_orders", RoleFilter(UserRole.SHOP))
async def show_current_orders_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Показать текущие (активные) заказы магазина."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    # Получаем активные заказы магазина (current=True)
    result = await orders_client.get_orders_history(token, current=True)

    if result.success and result.data:
        orders = result.data
        if orders:
            text = f"📦 <b>Текущие заказы ({len(orders)})</b>\n\n"
            for order in orders[:10]:  # Показываем максимум 10
                text += f"🔹 Заказ #{order.get('id', 'N/A')} — {order.get('status', 'N/A')}\n"
        else:
            text = "📦 У вас нет активных заказов."
    else:
        text = "❌ Не удалось получить список заказов."

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="shop_main_menu")]]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "show_order_history", RoleFilter(UserRole.SHOP))
async def show_order_history_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Показать историю заказов магазина."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    # Получаем завершённые заказы (используем get_orders_history с фильтром current=False)
    result = await orders_client.get_orders_history(token, current=False)

    if result.success and result.data:
        orders = result.data
        if orders:
            text = f"📋 <b>История заказов ({len(orders)})</b>\n\n"
            for order in orders[:10]:  # Показываем максимум 10
                text += f"🔹 Заказ #{order.get('id', 'N/A')} — {order.get('status', 'N/A')}\n"
        else:
            text = "📋 История заказов пуста."
    else:
        text = "❌ Не удалось получить историю заказов."

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="shop_main_menu")]]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(OrderStates.waiting_for_description)
async def order_description_handler(message: Message, state: FSMContext):
    """Обработка описания заказа."""
    await state.update_data(description=message.text)
    await state.set_state(OrderStates.waiting_for_pickup_address)
    await message.answer(OrderMessages.STEP_2_PICKUP)


@router.message(OrderStates.waiting_for_pickup_address)
async def order_pickup_handler(message: Message, state: FSMContext):
    """Обработка адреса забора."""
    await state.update_data(pickup_address=message.text)
    await state.set_state(OrderStates.waiting_for_delivery_address)
    await message.answer(OrderMessages.STEP_3_DELIVERY)


@router.message(OrderStates.waiting_for_delivery_address)
async def order_delivery_handler(message: Message, state: FSMContext):
    """Обработка адреса доставки."""
    await state.update_data(delivery_address=message.text)
    await state.set_state(OrderStates.waiting_for_price)
    await message.answer(OrderMessages.STEP_4_PRICE)


@router.message(OrderStates.waiting_for_price)
async def order_price_handler(message: Message, state: FSMContext):
    """Обработка цены и запрос на подтверждение."""
    price, error_message = service.validate_price(message.text)
    if error_message:
        await message.answer(error_message)
        return

    await state.update_data(price=price)
    data = await state.get_data()

    confirm_text, keyboard = service.format_order_confirmation(data)
    await state.set_state(OrderStates.confirmation)
    await message.answer(confirm_text, reply_markup=keyboard)


@router.callback_query(F.data == "order_confirm", OrderStates.confirmation)
async def order_confirm_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Подтверждение и создание заказа."""
    state_data = await state.get_data()

    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    await callback.message.edit_text(OrderMessages.CREATING_ORDER)

    response_text = await service.create_order(token, state_data, orders_client)
    await callback.message.edit_text(response_text)

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "order_cancel", OrderStates.confirmation)
async def order_cancel_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена создания заказа."""
    await state.clear()
    await callback.message.edit_text(OrderMessages.ORDER_CANCELLED)
    await callback.answer()
