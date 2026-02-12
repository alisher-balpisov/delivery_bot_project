"""Обработчики действий с заказами (отмена, завершение, редактирование)."""

import html
from collections.abc import Callable
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import OrderStatus, UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards.order_details import (
    get_shop_edit_menu_keyboard,
    get_shop_order_details_keyboard,
)
from bot.handlers.shop.messages import OrderActionsMessages
from bot.handlers.shop.orders.callbacks import OrderActionCallback, OrderDetailCallback
from bot.handlers.shop.states import OrderActionStates
from bot.handlers.shop.validators.price import validate_price
from bot.redis_storage import UserDataStorage
from bot.utils.api_helper import execute_api_call
from bot.utils.order_formatters import format_order_details
from bot.utils.token_manager import TokenManager

router = Router(name="shop_order_actions")


async def _initiate_edit(
    callback: CallbackQuery,
    state: FSMContext,
    target_state: Any,
    prompt_message: str,
):
    """Универсальная функция для старта редактирования поля."""
    order_id = OrderActionCallback.unpack(callback.data).order_id
    await state.set_state(target_state)
    await state.update_data(order_id=order_id)
    await callback.message.answer(prompt_message, parse_mode="HTML")
    await callback.answer()


async def _process_api_update(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
    func: Callable[..., Any],
    success_message: str,
    **kwargs: Any,
):
    """Универсальная функция для выполнения API-запроса на обновление."""
    data = await state.get_data()
    order_id = data.get("order_id")
    token_manager = TokenManager(auth_client, user_storage)

    result = await execute_api_call(
        token_manager,
        message.from_user.id,
        func,
        order_id=order_id,
        **kwargs,
    )

    if result.success:
        await message.answer(success_message)
        await state.clear()
    else:
        detail = result.detail or (
            result.data.get("detail") if result.data else "Неизвестная ошибка"
        )
        escaped_detail = html.escape(str(detail))
        await message.answer(f"❌ Ошибка: {escaped_detail}")


# =============================================================================
# Действия: Отмена, Завершение
# =============================================================================


@router.callback_query(OrderActionCallback.filter(F.action == "cancel"), RoleFilter(UserRole.SHOP))
async def shop_cancel_order_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderActionCallback,
):
    """Отмена заказа."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.update_order,
        order_id=order_id,
        data={"status": OrderStatus.CANCELED.value},
    )

    if result.success:
        await callback.answer("Заказ успешно отменен", show_alert=True)
        # Обновляем детали заказа
        new_callback_data = OrderDetailCallback(order_id=order_id)
        from bot.handlers.shop.orders.current.details import shop_order_details_handler

        await shop_order_details_handler(
            callback, auth_client, orders_client, user_storage, new_callback_data
        )
    else:
        error_msg = (
            result.data.get("detail", "Неизвестная ошибка") if result.data else "Ошибка сети"
        )
        await callback.answer(f"Ошибка при отмене заказа: {error_msg}", show_alert=True)


@router.callback_query(
    OrderActionCallback.filter(F.action == "complete"), RoleFilter(UserRole.SHOP)
)
async def shop_complete_order_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderActionCallback,
):
    """Завершение заказа."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.update_order,
        order_id=order_id,
        data={"status": OrderStatus.COMPLETED.value},
    )

    if result.success:
        await callback.answer("✅ Заказ успешно завершен", show_alert=True)
        new_callback_data = OrderDetailCallback(order_id=order_id)
        from bot.handlers.shop.orders.current.details import shop_order_details_handler

        await shop_order_details_handler(
            callback, auth_client, orders_client, user_storage, new_callback_data
        )
    else:
        error_msg = result.detail or "Ошибка при завершении заказа"
        await callback.answer(f"❌ {error_msg}", show_alert=True)


# =============================================================================
# Редактирование: Меню и Цена
# =============================================================================


@router.callback_query(OrderActionCallback.filter(F.action == "edit"), RoleFilter(UserRole.SHOP))
async def shop_edit_order_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderActionCallback,
):
    """Меню редактирования заказа."""
    await state.clear()
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    # Получаем заказ
    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success:
        await callback.answer("Не удалось загрузить заказ", show_alert=True)
        return

    order = result.data
    # back_callback returns to order details
    back_callback = OrderDetailCallback(order_id=order_id).pack()

    keyboard = get_shop_edit_menu_keyboard(
        order_id=order_id,
        back_callback=back_callback,
        can_edit_price=True,
        can_edit_description=True,
        can_edit_courier=False,
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование заказа #{order_id}</b>\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(
    OrderActionCallback.filter(F.action == "set_price"), RoleFilter(UserRole.SHOP)
)
async def shop_set_price_handler(
    callback: CallbackQuery,
    state: FSMContext,
    callback_data: OrderActionCallback,
):
    """Инициация установки цены."""
    await _initiate_edit(
        callback,
        state,
        OrderActionStates.waiting_for_price,
        "💰 <b>Укажите стоимость доставки</b>\n\n"
        "Введите сумму в тенге (только цифры).\n"
        "<i>Минимальная стоимость: 3000 ₸</i>",
    )


@router.message(OrderActionStates.waiting_for_price, RoleFilter(UserRole.SHOP))
async def process_order_price_update(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Обработка ввода цены."""
    price, error = validate_price(message.text)
    if error:
        await message.answer(error)
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    await _process_api_update(
        message,
        state,
        auth_client,
        user_storage,
        orders_client.update_order,
        f"✅ Цена заказа #{order_id} установлена: {price} ₸",
        data={"price": price},
    )


# =============================================================================
# Редактирование: Заметка
# =============================================================================


@router.callback_query(
    OrderActionCallback.filter(F.action == "add_note"), RoleFilter(UserRole.SHOP)
)
async def shop_add_note_handler(
    callback: CallbackQuery,
    state: FSMContext,
    callback_data: OrderActionCallback,
):
    """Инициация добавления заметки."""
    await _initiate_edit(
        callback,
        state,
        OrderActionStates.waiting_for_note,
        OrderActionsMessages.ADD_NOTE_PROMPT,
    )


@router.message(OrderActionStates.waiting_for_note, RoleFilter(UserRole.SHOP))
async def process_order_note_add(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Обработка добавления заметки."""
    content = message.text.strip()
    if not content:
        await message.answer("⚠️ Текст заметки не может быть пустым.")
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    await _process_api_update(
        message,
        state,
        auth_client,
        user_storage,
        orders_client.add_order_note,
        f"✅ Заметка к заказу #{order_id} добавлена.",
        content=content,
    )


# =============================================================================
# Редактирование: Описание
# =============================================================================


@router.callback_query(
    OrderActionCallback.filter(F.action == "edit_order_description"), RoleFilter(UserRole.SHOP)
)
async def shop_edit_description_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderActionCallback,
):
    """Инициация изменения описания с предпросмотром."""
    order_id = callback_data.order_id
    token_manager = TokenManager(auth_client, user_storage)

    # Получаем текущие данные заказа
    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success:
        await callback.answer("Не удалось загрузить данные заказа", show_alert=True)
        return

    order = result.data
    current_description = order.get("description", "")

    text = OrderActionsMessages.EDIT_DESCRIPTION_PROMPT.format(
        current=html.escape(current_description)
    )

    # Кнопка отмены возвращает в меню редактирования
    cancel_callback = OrderActionCallback(order_id=order_id, action="edit").pack()

    await callback.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_callback)]
            ]
        ),
        parse_mode="HTML",
    )

    await state.set_state(OrderActionStates.waiting_for_description)
    await state.update_data(order_id=order_id)
    await callback.answer()


@router.message(OrderActionStates.waiting_for_description, RoleFilter(UserRole.SHOP))
async def process_order_description_update(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Обработка изменения описания."""
    new_description = message.text.strip()
    if not new_description:
        await message.answer("⚠️ Описание не может быть пустым.")
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    token_manager = TokenManager(auth_client, user_storage)

    # Обновляем описание
    result = await execute_api_call(
        token_manager,
        message.from_user.id,
        orders_client.update_order,
        order_id=order_id,
        data={"description": new_description},
    )

    if not result.success:
        error_msg = result.detail or (
            result.data.get("detail") if result.data else "Неизвестная ошибка"
        )
        await message.answer(f"❌ Ошибка при обновлении описания: {html.escape(str(error_msg))}")
        return

    # Получаем обновленные детали
    result = await execute_api_call(
        token_manager,
        message.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success or not result.data:
        await message.answer("✅ Описание обновлено, но не удалось загрузить детали заказа.")
        await state.clear()
        return

    order = result.data
    text = format_order_details(order, role=UserRole.SHOP.value)

    # Кнопка "Назад" в список заказов
    from bot.handlers.shop.orders.callbacks import OrdersListCallback

    back_callback = OrdersListCallback(page=1, status="all").pack()

    keyboard = get_shop_order_details_keyboard(
        order_id=order_id,
        status=order.get("status"),
        back_callback=back_callback,
        courier_id=order.get("courier_id")
        or (order.get("courier").get("id") if order.get("courier") else None),
        dispute_id=order.get("dispute_id"),
        has_price=order.get("price") is not None,
    )

    await message.answer(
        f"✅ Описание обновлено.\n\n{text}", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.clear()


# =============================================================================
# Заглушки
# =============================================================================


@router.callback_query(
    OrderActionCallback.filter(F.action == "change_courier"), RoleFilter(UserRole.SHOP)
)
async def shop_change_courier_handler(callback: CallbackQuery):
    """Заглушка для смены курьера."""
    await callback.answer("Функция смены курьера в разработке", show_alert=True)


@router.callback_query(
    OrderActionCallback.filter(F.action.in_(["view_dispute", "open_dispute"])),
    RoleFilter(UserRole.SHOP),
)
async def shop_action_placeholder_handler(callback: CallbackQuery):
    """Заглушка для споров."""
    await callback.answer("Этот функционал будет доступен в ближайшем обновлении", show_alert=True)
