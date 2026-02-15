"""Обработчики создания спора."""

import html

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.disputes_client import DisputesClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.messages import DisputeMessages, OrderActionsMessages
from bot.handlers.shop.orders.callbacks import DisputeReasonCallback, OrderActionCallback
from bot.handlers.shop.orders.dispute.keyboards import (
    get_dispute_created_keyboard,
    get_dispute_reason_keyboard,
    get_pre_dispute_keyboard,
)
from bot.handlers.shop.orders.dispute.router import router
from bot.handlers.shop.orders.dispute.states import DisputeStates
from bot.redis_storage import UserDataStorage
from bot.utils.api_helper import execute_api_call
from bot.utils.token_manager import TokenManager

# =============================================================================
# 1. Открытие спора (Pre-dispute)
# =============================================================================


@router.callback_query(
    OrderActionCallback.filter(F.action == "open_dispute"), RoleFilter(UserRole.SHOP)
)
async def shop_start_dispute_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderActionCallback,
):
    """Начало процесса спора: показ контактов."""
    order_id = callback_data.order_id
    page = callback_data.page
    status = callback_data.status

    token_manager = TokenManager(auth_client, user_storage)

    # Получаем детали заказа для контактов
    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success or not result.data:
        await callback.answer("Не удалось загрузить данные заказа", show_alert=True)
        return

    order = result.data

    # Определяем контакты второй стороны (Курьера)
    other_side_role = "Курьера"
    courier = order.get("courier")  # CourierInfoForShop
    phone = "Не указан"

    if courier and courier.get("phone_number"):
        # Берем первый номер
        phone = courier.get("phone_number")[0]

    text = DisputeMessages.PRE_DISPUTE_WARNING.format(
        order_id=order_id,
        order_description=html.escape(order.get("description") or "Нет описания"),
        other_side_role=other_side_role,
        phone=phone,
    )

    keyboard = get_pre_dispute_keyboard(order_id, page=page, status=status)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# =============================================================================
# 2. Переход к вводу причины
# =============================================================================


@router.callback_query(
    OrderActionCallback.filter(F.action == "dispute_next"), RoleFilter(UserRole.SHOP)
)
async def shop_dispute_enter_reason_handler(
    callback: CallbackQuery,
    state: FSMContext,
    callback_data: OrderActionCallback,
):
    """Запрос причины спора."""
    order_id = callback_data.order_id
    page = callback_data.page
    status = callback_data.status

    await state.set_state(DisputeStates.waiting_for_reason)
    # Сохраняем контекст в state для текстового ввода
    await state.update_data(order_id=order_id, page=page, status=status)

    # Используем edit_text с inline клавиатурой причин
    keyboard = get_dispute_reason_keyboard(order_id, page=page, status=status)

    await callback.message.edit_text(
        f"{DisputeMessages.REASON_PROMPT}\n\nВыберите из списка или напишите сообщение.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


# =============================================================================
# 3. Обработка причины (Inline Callback)
# =============================================================================


@router.callback_query(DisputeReasonCallback.filter(), RoleFilter(UserRole.SHOP))
async def shop_process_dispute_reason_callback(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: DisputeReasonCallback,
):
    """Создание спора через выбор причины."""
    # Словарь причин (дубликат из клавиатуры, лучше вынести в константы)
    reasons = {
        1: "Курьер сильно задерживает заказ",
        2: "Курьер нагрубил получателю",
        3: "Курьер не доставил заказ",
        4: "Курьер повредил заказ",
    }

    description = reasons.get(callback_data.reason_id, "Другая причина")

    await _create_dispute(
        message=callback.message,
        user_id=callback.from_user.id,
        order_id=callback_data.order_id,
        description=description,
        page=callback_data.page,
        status=callback_data.status,
        state=state,
        auth_client=auth_client,
        disputes_client=disputes_client,
        user_storage=user_storage,
    )
    await callback.answer()


# =============================================================================
# 3b. Обработка причины (Текстовое сообщение)
# =============================================================================


@router.message(DisputeStates.waiting_for_reason, RoleFilter(UserRole.SHOP))
async def shop_process_dispute_message_handler(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Создание спора через текстовое сообщение."""
    description = message.text.strip()
    if not description:
        await message.answer("⚠️ Описание не может быть пустым.")
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    page = data.get("page", 1)
    status = data.get("status", "all")

    await _create_dispute(
        message=message,
        user_id=message.from_user.id,
        order_id=order_id,
        description=description,
        page=page,
        status=status,
        state=state,
        auth_client=auth_client,
        disputes_client=disputes_client,
        user_storage=user_storage,
    )


async def _create_dispute(
    message: Message,
    user_id: int,
    order_id: int,
    description: str,
    page: int,
    status: str,
    state: FSMContext,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    user_storage: UserDataStorage,
):
    """Вспомогательная функция для создания спора."""
    token_manager = TokenManager(auth_client, user_storage)

    # Индикация загрузки (редактируем сообщение если возможно, иначе новое)
    try:
        if message.from_user.is_bot:  # Это сообщение бота (edit)
            await message.edit_text("⏳ Создаем спор...")
        else:
            temp_msg = await message.answer("⏳ Создаем спор...")
    except Exception:
        pass

    # Создаем спор
    result = await execute_api_call(
        token_manager,
        user_id,
        disputes_client.create_dispute,
        dispute_data={"order_id": order_id, "description": html.escape(description)},
    )

    if not result.success:
        error_detail = result.detail
        error_text = "Неизвестная ошибка"

        if isinstance(error_detail, list):
            for err in error_detail:
                if err.get("type") == "string_too_short":
                    min_len = err.get("ctx", {}).get("min_length", 10)
                    msg_text = f"⚠️ Описание слишком короткое (минимум {min_len} символов)."
                    await _send_or_edit(message, msg_text)
                    return
        elif error_detail:
            error_text = str(error_detail)

        msg_text = f"❌ {OrderActionsMessages.DISPUTE_ERROR.format(error=html.escape(error_text))}"
        await _send_or_edit(message, msg_text)
        return

    dispute = result.data
    dispute_id = dispute.get("id")

    # Если это сообщение пользователя, удаляем temp_msg (сложно передать).
    # Просто постим новое сообщение

    text = DisputeMessages.CREATED_SUCCESS
    keyboard = get_dispute_created_keyboard(order_id, dispute_id, page=page, status=status)

    await _send_or_edit(message, text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()


async def _send_or_edit(message: Message, text: str, reply_markup=None, parse_mode=None):
    """Отправляет или редактирует сообщение."""
    try:
        # Пытаемся редактировать только если это сообщение бота
        # Но message переданный в _create_dispute может быть от пользователя
        if message.from_user.is_bot:
            await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
