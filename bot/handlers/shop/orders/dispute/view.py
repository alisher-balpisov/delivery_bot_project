"""Обработчики просмотра спора."""

import html

from aiogram import F
from aiogram.types import CallbackQuery
from backend.src.common.enums import DisputeStatus, UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.disputes_client import DisputesClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.messages import DisputeMessages
from bot.handlers.shop.orders.callbacks import OrderActionCallback, OrderRefundCallback
from bot.handlers.shop.orders.dispute.keyboards import get_dispute_card_keyboard
from bot.handlers.shop.orders.dispute.router import router
from bot.redis_storage import UserDataStorage
from bot.utils.api_helper import execute_api_call
from bot.utils.token_manager import TokenManager

# =============================================================================
# 4. Карточка спора
# =============================================================================


@router.callback_query(
    OrderActionCallback.filter(F.action == "view_dispute"), RoleFilter(UserRole.SHOP)
)
async def shop_dispute_card_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderActionCallback,
):
    """Отображение карточек всех споров по заказу."""
    order_id = callback_data.order_id
    page = callback_data.page
    status = callback_data.status

    token_manager = TokenManager(auth_client, user_storage)

    # 1. Получаем детали заказа
    order_result = await execute_api_call(
        token_manager, callback.from_user.id, orders_client.get_order_details, order_id=order_id
    )

    if not order_result.success or not order_result.data:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    order = order_result.data
    dispute_ids: list[int] = order.get("dispute_ids", [])

    if not dispute_ids:
        await callback.answer("Споры не найдены", show_alert=True)
        return

    # 2. Собираем данные обо всех спорах
    all_disputes = []
    for d_id in dispute_ids:
        res = await execute_api_call(
            token_manager,
            callback.from_user.id,
            disputes_client.get_dispute_details,
            dispute_id=d_id,
        )
        if res.success and res.data:
            all_disputes.append(res.data)

    if not all_disputes:
        await callback.answer("Не удалось загрузить детали споров", show_alert=True)
        return

    # 3. Формируем общий текст сообщения
    status_map = {
        "PENDING_REVIEW": "⏳ На рассмотрении",
        "IN_REVIEW": "👀 В работе",
        "RESOLVED": "✅ Решен",
        "CANCELLED": "🚫 Отменен",
    }

    # Общая информация о заказе (заголовок)
    header_text = f"<b>📦 Спор по заказу #{order_id}</b>\n"
    header_text += f"Описание заказа: {html.escape(order.get('description') or 'Нет')}\n"
    header_text += f"Курьер: {order.get('courier_full_name') or 'Не назначен'}\n"
    header_text += "--------------------------\n"

    disputes_blocks = []
    for dispute in all_disputes:
        d_status = status_map.get(dispute.get("status"), dispute.get("status"))

        # Формируем блок для каждого отдельного спора
        block = (
            f"<b>🆔 Спор #{dispute.get('id')}</b>\n"
            f"👤 Кем открыт: {dispute.get('opened_by_role')}\n"
            f"📝 Описание спора: {html.escape(dispute.get('description') or 'Нет описания')}\n"
            f"📊 Статус: {d_status}\n"
        )
        disputes_blocks.append(block)

    # Соединяем всё в одну строку
    full_text = header_text + "\n".join(disputes_blocks)

    # 4. Работа с клавиатурой
    # Если спор один — оставляем стандартную логику.
    # Если несколько — можно передать ID последнего или переделать функцию под список.
    # Для примера берем ID первого спора для кнопок действий.
    main_dispute_id = all_disputes[0].get("id")

    # Логика возможности отмены (для примера по первому спору)
    can_cancel = (
        all_disputes[0].get("opened_by_role") == UserRole.SHOP
        and all_disputes[0].get("status") in DisputeStatus.active_statuses()
    )

    keyboard = get_dispute_card_keyboard(
        order_id, main_dispute_id, can_cancel, page=page, status=status, source=callback_data.source
    )

    try:
        await callback.message.edit_text(full_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(full_text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


# =============================================================================
# 5. Отмена спора
# =============================================================================


@router.callback_query(
    OrderRefundCallback.filter(F.action == "cancel_dispute"), RoleFilter(UserRole.SHOP)
)
async def shop_cancel_dispute_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrderRefundCallback,
):
    """Отмена спора."""
    dispute_id = callback_data.dispute_id
    token_manager = TokenManager(auth_client, user_storage)

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        disputes_client.update_dispute_status,
        dispute_id=dispute_id,
        status_data={"status": DisputeStatus.CANCELLED.value},
    )

    if result.success:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="shop_main_menu")]
            ]
        )

        await callback.message.edit_text(
            DisputeMessages.CANCELLED,
            reply_markup=kb,
        )

    else:
        await callback.answer(f"Ошибка: {result.detail}", show_alert=True)
