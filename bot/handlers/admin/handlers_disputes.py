# handlers_disputes.py — Хендлеры раздела споров (для админа)
"""
Модуль обработки споров в админ-панели Telegram-бота.

Реализует:
- Просмотр списка споров с пагинацией и фильтрацией
- Детальный просмотр отдельного спора
- Управление статусом спора (в работу, разрешить, отменить)
"""

from collections.abc import Callable
from contextlib import suppress
from typing import Any

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from bot.clients.admin_client import AdminClient
from bot.clients.auth_client import AuthClient
from bot.filters.filters import RoleFilter
from bot.handlers.admin.messages import AdminMessages as AM
from bot.keyboards.admin import (
    DISPUTE_STATUS_EMOJIS,
    DISPUTE_STATUS_LABELS,
    get_dispute_details_keyboard,
    get_disputes_list_keyboard,
)
from bot.redis_storage import UserDataStorage
from bot.utils.formatters import format_dt_short
from bot.utils.token_manager import TokenManager

logger = get_logger(__name__)

router = Router(name="admin_disputes_handlers")
router.message.filter(RoleFilter(UserRole.ADMIN))
router.callback_query.filter(RoleFilter(UserRole.ADMIN))

DISPUTES_PER_PAGE = 5


# ==================== CallbackData классы ====================


class DisputesListCallback(CallbackData, prefix="admin_disputes"):
    """CallbackData для списка споров."""

    page: int = 1
    status: str = "all"  # all, pending_review, in_review, resolved, cancelled


class DisputeDetailCallback(CallbackData, prefix="admin_dispute_det"):
    """CallbackData для детального просмотра спора."""

    dispute_id: int
    from_page: int = 1
    from_status: str = "all"


class DisputeActionCallback(CallbackData, prefix="admin_dispute_act"):
    """CallbackData для действий над спором."""

    dispute_id: int
    action: str  # in_review, resolve, cancel


# ==================== Вспомогательные функции ====================


async def execute_api_call(
    token_manager: TokenManager, user_id: int, func: Callable[..., Any], **kwargs
) -> Any:
    """
    Выполняет API-запрос с автоматическим обновлением токена при 401 ошибке.
    """
    token = await token_manager.get_token(user_id)
    result = await func(token=token, **kwargs)

    if result.status_code == 401:
        token = await token_manager.get_token(user_id, force_refresh=True)
        if token:
            result = await func(token=token, **kwargs)

    return result


def format_role_name(role: str) -> str:
    """Преобразует роль пользователя в читаемый формат."""
    role_names = {
        "shop": "🏪 Магазин",
        "courier": "👤 Курьер",
        "admin": "👑 Администратор",
    }
    return role_names.get(role.lower(), role)


def format_dispute_details(dispute: dict) -> str:
    """
    Форматирует детали спора для отображения.

    Args:
        dispute: Словарь с данными спора

    Returns:
        Отформатированная строка с деталями спора
    """
    dispute_id = dispute.get("id")
    order_id = dispute.get("order_id")
    status = dispute.get("status", "unknown")
    shop_name = dispute.get("shop_name") or "Не указан"
    full_name = dispute.get("courier_full_name")
    courier_name = full_name.split()[1] if full_name else "Не указан"
    opened_by_role = dispute.get("opened_by_role", "unknown")
    description = dispute.get("description", "Нет описания")
    created_at = format_dt_short(dispute.get("created_at", ""))
    resolved_at = dispute.get("resolved_at")

    # Эмодзи и читаемый статус
    status_emoji = DISPUTE_STATUS_EMOJIS.get(status, "⚪")
    status_label = DISPUTE_STATUS_LABELS.get(status, status)

    # Форматируем дату разрешения
    resolved_at_str = format_dt_short(resolved_at) if resolved_at else "—"

    return AM.DISPUTE_DETAILS_TEMPLATE.format(
        dispute_id=dispute_id,
        order_id=order_id,
        status_emoji=status_emoji,
        status=status_label,
        shop_name=shop_name,
        courier_name=courier_name,
        opened_by_role=format_role_name(opened_by_role),
        created_at=created_at,
        resolved_at=resolved_at_str,
        description=description,
    )


# ==================== Хендлеры ====================


@router.callback_query(F.data == "show_disputes")
@router.callback_query(DisputesListCallback.filter())
async def show_disputes_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
    callback_data: DisputesListCallback | None = None,
):
    """
    Отображает список споров с пагинацией и фильтрацией.

    Обрабатывает:
    - Первичный вход через callback "show_disputes"
    - Переход по страницам через DisputesListCallback
    - Фильтрацию по статусу спора
    """
    # Если запущен через "show_disputes" (меню), создаем дефолтный объект
    if callback_data is None:
        callback_data = DisputesListCallback(page=1, status="all")

    page = callback_data.page
    filter_status = callback_data.status

    token_manager = TokenManager(auth_client, user_storage)

    # Логика маппинга фильтра в параметр API
    api_status = None if filter_status == "all" else filter_status

    # Выполняем запрос через безопасную обертку
    result = await execute_api_call(
        token_manager=token_manager,
        user_id=callback.from_user.id,
        func=admin_client.get_disputes,
        page=page,
        limit=DISPUTES_PER_PAGE,
        status=api_status,
    )

    if not result.success:
        error_msg = result.data.get("detail", "Ошибка API") if result.data else "Неизвестная ошибка"
        logger.error(f"Error fetching disputes: {error_msg}")
        await callback.answer(f"Не удалось загрузить споры: {error_msg}", show_alert=True)
        return

    data = result.data
    disputes = data.get("items", [])
    total_count = data.get("total", 0)
    total_pages = max(1, data.get("pages", 1))

    # Фабрики для генерации callback_data кнопок внутри клавиатуры
    def callback_factory(action: str, p: int, dispute_id: int | None) -> str:
        if action == "dispute_detail":
            return DisputeDetailCallback(
                dispute_id=dispute_id,
                from_page=page,
                from_status=filter_status or "all",
            ).pack()
        elif action == "disputes_page":
            return DisputesListCallback(page=p, status=filter_status).pack()
        return "noop"

    def filter_callback_factory(status: str) -> str:
        # При переключении фильтра сбрасываем на 1 страницу
        return DisputesListCallback(page=1, status=status).pack()

    keyboard = get_disputes_list_keyboard(
        disputes=disputes,
        page=page,
        total_pages=total_pages,
        filter_status=filter_status,
        callback_factory=callback_factory,
        filter_callback_factory=filter_callback_factory,
    )

    text = AM.DISPUTES_LIST_TITLE.format(total_count=total_count)

    # Если споров нет, добавляем соответствующее сообщение
    if not disputes:
        text += f"\n\n{AM.NO_DISPUTES_FOUND}"

    # Используем suppress для игнорирования ошибки, если текст не изменился
    with suppress(Exception):
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(DisputeDetailCallback.filter())
async def dispute_details_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
    callback_data: DisputeDetailCallback,
):
    """Отображает детали конкретного спора."""
    token_manager = TokenManager(auth_client, user_storage)
    dispute_id = callback_data.dispute_id

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        admin_client.get_dispute_details,
        dispute_id=dispute_id,
    )

    if not result.success or not result.data:
        await callback.answer(AM.DISPUTE_NOT_FOUND, show_alert=True)
        return

    dispute = result.data

    # Формирование текста
    text = format_dispute_details(dispute)

    # Формируем кнопку назад с учетом сохраненного состояния (страница, фильтр)
    back_callback = DisputesListCallback(
        page=callback_data.from_page, status=callback_data.from_status
    ).pack()

    keyboard = get_dispute_details_keyboard(
        dispute_id=dispute_id,
        shop_name=dispute.get("shop_name") or "Не указан",
        courier_name=dispute.get("courier_full_name") or "Не указан",
        shop_id=dispute.get("shop_id"),
        courier_id=dispute.get("courier_id"),
        dispute_status=dispute.get("status"),
        back_callback_data=back_callback,
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("dispute_action_"))
async def dispute_action_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """
    Обрабатывает действия над спором: смена статуса.

    Обрабатывает callback_data формата: dispute_action_{dispute_id}_{action}
    где action: in_review, resolve, cancel
    """
    # Парсим callback_data
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("Неверный формат данных", show_alert=True)
        return

    try:
        dispute_id = int(parts[2])
        action = parts[3]
    except (ValueError, IndexError):
        await callback.answer("Ошибка обработки действия", show_alert=True)
        return

    token_manager = TokenManager(auth_client, user_storage)

    # Маппинг действий в статусы
    action_to_status = {
        "in_review": "in_review",
        "resolve": "resolved",
        "cancel": "cancelled",
    }

    new_status = action_to_status.get(action)
    if not new_status:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    # Подготовка данных для обновления
    update_data = {"status": new_status}

    # Для разрешения и отмены нужно добавить resolution_notes
    if action == "resolve":
        update_data["resolution_notes"] = "Спор разрешён администратором."
    elif action == "cancel":
        update_data["resolution_notes"] = "Спор отменён администратором."

    # Выполняем запрос на обновление
    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        admin_client.update_dispute_status,
        dispute_id=dispute_id,
        data=update_data,
    )

    if result.success:
        await callback.answer(AM.DISPUTE_STATUS_UPDATED, show_alert=True)

        # Обновляем детали спора
        detail_callback = DisputeDetailCallback(dispute_id=dispute_id)
        await dispute_details_handler(
            callback, auth_client, admin_client, user_storage, detail_callback
        )
    else:
        error_msg = (
            result.data.get("detail", "Неизвестная ошибка") if result.data else "Ошибка сети"
        )
        await callback.answer(f"{AM.DISPUTE_STATUS_UPDATE_ERROR}: {error_msg}", show_alert=True)
