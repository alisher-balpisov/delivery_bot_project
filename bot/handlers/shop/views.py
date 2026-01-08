from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.constants import UserRole
from bot.filters.filters import RoleFilter
from bot.messages import OrderMessages
from bot.redis_storage import UserDataStorage
from bot.states import OrderStates
from bot.utils.token_manager import TokenManager

shop_router = Router(name="shop_handlers")


@shop_router.message(Command("new_order"), RoleFilter(UserRole.SHOP))
async def new_order_handler(message: Message, state: FSMContext):
    """Начать создание нового заказа."""
    await state.set_state(OrderStates.waiting_for_description)
    await message.answer(OrderMessages.STEP_1_DESCRIPTION)


@shop_router.message(OrderStates.waiting_for_description)
async def order_description_handler(message: Message, state: FSMContext):
    """Обработка описания заказа."""
    await state.update_data(description=message.text)
    await state.set_state(OrderStates.waiting_for_pickup_address)
    await message.answer(OrderMessages.STEP_2_PICKUP)


@shop_router.message(OrderStates.waiting_for_pickup_address)
async def order_pickup_handler(message: Message, state: FSMContext):
    """Обработка адреса забора."""
    await state.update_data(pickup_address=message.text)
    await state.set_state(OrderStates.waiting_for_delivery_address)
    await message.answer(OrderMessages.STEP_3_DELIVERY)


@shop_router.message(OrderStates.waiting_for_delivery_address)
async def order_delivery_handler(message: Message, state: FSMContext):
    """Обработка адреса доставки."""
    await state.update_data(delivery_address=message.text)
    await state.set_state(OrderStates.waiting_for_price)
    await message.answer(OrderMessages.STEP_4_PRICE)


@shop_router.message(OrderStates.waiting_for_price)
async def order_price_handler(message: Message, state: FSMContext):
    """Обработка цены и запрос на подтверждение."""
    from bot.handlers.shop import service

    price, error_message = service.validate_price(message.text)
    if error_message:
        await message.answer(error_message)
        return

    await state.update_data(price=price)
    data = await state.get_data()

    confirm_text, keyboard = service.format_order_confirmation(data)
    await state.set_state(OrderStates.confirmation)
    await message.answer(confirm_text, reply_markup=keyboard)


@shop_router.callback_query(F.data == "order_confirm", OrderStates.confirmation)
async def order_confirm_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Подтверждение и создание заказа."""
    state_data = await state.get_data()

    # Создаем TokenManager
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    await callback.message.edit_text(OrderMessages.CREATING_ORDER)

    from bot.handlers.shop import service

    response_text = await service.create_order(token, state_data, orders_client)
    await callback.message.edit_text(response_text)

    await state.clear()
    await callback.answer()


@shop_router.callback_query(F.data == "order_cancel", OrderStates.confirmation)
async def order_cancel_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена создания заказа."""
    await state.clear()
    await callback.message.edit_text(OrderMessages.ORDER_CANCELLED)
    await callback.answer()
