"""Обработчики выбора курьера для заказа."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.couriers_client import CouriersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.formatters.order import format_order_confirmation
from bot.handlers.shop.keyboards.create_order import (
    get_confirmation_keyboard,
    get_courier_selection_keyboard,
)
from bot.handlers.shop.messages import OrderCreateMessages
from bot.handlers.shop.orders.callbacks import CourierSelectionCallback
from bot.handlers.shop.states import OrderCreateStates
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

router = Router(name="order_create_courier")


async def request_courier_selection(
    message: Message, state: FSMContext, token: str, couriers_client: CouriersClient, page: int = 1
):
    """Запросить выбор курьера."""
    await message.answer("⏳ Загружаем список курьеров...")
    result = await couriers_client.get_active_couriers_for_selection(token, page=page)

    if result.success and isinstance(result.data, dict) and result.data.get("items"):
        items = result.data["items"]
        total = result.data["total"]

        await message.answer(
            OrderCreateMessages.COURIER_SELECTION,
            reply_markup=get_courier_selection_keyboard(items, page=1, total=total),
            parse_mode="HTML",
        )
        await state.set_state(OrderCreateStates.waiting_for_courier)
    elif result.success and isinstance(result.data, list) and len(result.data) > 0:
        # Fallback для старого формата
        await message.answer(
            OrderCreateMessages.COURIER_SELECTION,
            reply_markup=get_courier_selection_keyboard(result.data),
            parse_mode="HTML",
        )
        await state.set_state(OrderCreateStates.waiting_for_courier)
    else:
        # Нет курьеров
        msg = "⚠️ В данный момент нет свободных курьеров."
        if not result.success:
            msg = "⚠️ Не удалось загрузить список курьеров."

        await message.answer(
            f"{msg}\n"
            "Заказ будет создан в режиме ожидания курьера (система подберет первого освободившегося).",
            parse_mode="HTML",
        )
        await state.update_data(courier_id=None)
        await _proceed_to_confirmation(message, state)


@router.callback_query(
    CourierSelectionCallback.filter(F.courier_id == -1), RoleFilter(UserRole.SHOP)
)
async def pagination_courier_handler(
    callback: CallbackQuery,
    callback_data: CourierSelectionCallback,
    state: FSMContext,
    couriers_client: CouriersClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Пагинация при выборе курьера."""
    page = callback_data.page
    telegram_id = callback.from_user.id
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(telegram_id)

    if not token:
        await callback.answer("⚠️ Ошибка авторизации", show_alert=True)
        return

    result = await couriers_client.get_active_couriers_for_selection(token, page=page)

    if result.success and isinstance(result.data, dict) and result.data.get("items"):
        items = result.data["items"]
        total = result.data["total"]

        await callback.message.edit_reply_markup(
            reply_markup=get_courier_selection_keyboard(items, page=page, total=total)
        )
    else:
        await callback.answer("⚠️ Не удалось загрузить страницу", show_alert=True)

    await callback.answer()


@router.callback_query(CourierSelectionCallback.filter(), RoleFilter(UserRole.SHOP))
async def select_courier_handler(
    callback: CallbackQuery,
    callback_data: CourierSelectionCallback,
    state: FSMContext,
    couriers_client: CouriersClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Обработка выбора курьера."""
    courier_id = callback_data.courier_id
    courier_name = None

    # 0 означает автовыбор
    if courier_id == 0:
        await state.update_data(courier_id=None, courier_name=None)
        await callback.answer("Курьер будет подобран автоматически")
    else:
        # Получаем имя курьера
        telegram_id = callback.from_user.id
        token_manager = TokenManager(auth_client, user_storage)
        token = await token_manager.get_token(telegram_id)

        if token:
            courier_info = await couriers_client.get_courier_details(token, courier_id)
            if courier_info.success and courier_info.data:
                courier_name = courier_info.data.get("full_name")

        await state.update_data(courier_id=courier_id, courier_name=courier_name)
        await callback.answer(f"Выбран курьер: {courier_name}")

    # Переход к подтверждению
    data = await state.get_data()
    text = format_order_confirmation(
        description=data.get("description", ""),
        order_type=data.get("order_type"),
        price=data.get("price"),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderCreateStates.confirmation)


async def _proceed_to_confirmation(message: Message, state: FSMContext):
    """Переход к подтверждению."""
    from backend.src.common.enums import OrderType

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
