"""Обработчики деталей заказа."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards.order_details import get_shop_order_details_keyboard
from bot.handlers.shop.messages import OrderListMessages
from bot.handlers.shop.orders.callbacks import (
    OrderActionCallback,
    OrderDetailCallback,
    OrdersListCallback,
)
from bot.redis_storage import UserDataStorage
from bot.utils.api_helper import execute_api_call
from bot.utils.formatters import format_courier_card
from bot.utils.order_formatters import format_order_details
from bot.utils.token_manager import TokenManager

router = Router(name="shop_order_details")


@router.callback_query(OrderDetailCallback.filter(), RoleFilter(UserRole.SHOP))
async def shop_order_details_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderDetailCallback,
):
    """Отображение деталей заказа."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success or not result.data:
        await callback.answer(OrderListMessages.ORDER_NOT_FOUND, show_alert=True)
        return

    order = result.data

    # Формирование текста
    text = format_order_details(order)

    # Кнопка назад с сохранением контекста
    back_callback = OrdersListCallback(
        page=callback_data.from_page, status=callback_data.from_status
    ).pack()

    keyboard = get_shop_order_details_keyboard(
        order_id=order_id,
        status=order.get("status"),
        back_callback=back_callback,
        courier_id=order.get("courier_id")
        or (order.get("courier").get("id") if order.get("courier") else None),
        dispute_id=order.get("dispute_id"),
        has_price=order.get("price") is not None,
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(
    OrderActionCallback.filter(F.action == "view_courier"), RoleFilter(UserRole.SHOP)
)
async def shop_view_courier_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderActionCallback,
):
    """Отображение информации о курьере."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success or not result.data:
        await callback.answer(OrderListMessages.ORDER_NOT_FOUND, show_alert=True)
        return

    order = result.data
    courier = order.get("courier")

    if not courier:
        await callback.answer("Курьер не назначен", show_alert=True)
        return

    text = format_courier_card(courier)

    # Кнопка назад к деталям заказа
    back_callback = OrderDetailCallback(order_id=order_id).pack()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()
