import asyncio

from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.admin_client import AdminClient
from bot.clients.system_client import SystemClient
from bot.constants import STATS_TIMEOUT
from bot.exceptions import ErrorMessages
from bot.keyboards.admin import get_admin_main_keyboard, get_back_to_menu_keyboard
from bot.messages import AdminMessages, AdminServiceMessages, CommonMessages
from bot.utils.formatters import format_codes_as_html_table
from bot.utils.helpers import format_stats_message

logger = get_logger(__name__)


async def show_admin_main_menu(
    event: CallbackQuery | Message,
    admin_name: str,
    admin_client: AdminClient | None = None,
    token: str | None = None,
):
    """Показывает главное меню администратора с динамической статистикой."""
    from bot.handlers.admin.messages import AdminMessages as AM

    # Получаем статистику, если переданы клиент и токен
    stats_text = ""
    if admin_client and token:
        try:
            result = await admin_client.get_system_stats(token)
            if result.success and isinstance(result.data, dict):
                stats = result.data
                stats_text = AM.ADMIN_MAIN_MENU.format(
                    active_orders=stats.get("active_orders", 0),
                    active_couriers=stats.get("active_couriers", 0),
                    orders_today=stats.get("orders_today", 0),
                    active_disputes=stats.get("unresolved_disputes", 0),
                )
            else:
                # Если не удалось получить статистику, показываем простое приветствие
                stats_text = f"👑 Привет, администратор {admin_name}!"
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}", exc_info=True)
            stats_text = f"👑 Привет, администратор {admin_name}!"
    else:
        # Если клиент или токен не переданы, показываем простое приветствие
        stats_text = f"👑 Привет, администратор {admin_name}!"

    keyboard = get_admin_main_keyboard()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(stats_text, reply_markup=keyboard)
        await event.answer()
    else:
        await event.answer(stats_text, reply_markup=keyboard)


async def create_registration_code(
    token: str | None,
    admin_client: AdminClient,
    role: UserRole,
) -> str:
    """Создает регистрационный код для указанной роли."""
    if not token:
        return ErrorMessages.Auth.UNAUTHORIZED
    try:
        result = await admin_client.create_registration_code(token, role)
        if result.success and isinstance(result.data, dict) and result.data.get("code"):
            code = result.data["code"]
            return AdminMessages.CODE_CREATED.format(role.value.upper(), code)
        else:
            error_detail = result.detail or AdminServiceMessages.CONNECTION_ERROR
            return ErrorMessages.Codes.CODE_CREATION_ERROR(detail=error_detail)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании кода для {role.value}: {e}", exc_info=True)
        return ErrorMessages.Codes.CODE_CREATION_ERROR(detail=AdminServiceMessages.INTERNAL_ERROR)


async def get_formatted_codes(token: str | None, admin_client: AdminClient) -> str:
    """Получает коды из API и форматирует их."""
    if not token:
        return ErrorMessages.Auth.UNAUTHORIZED
    try:
        result = await admin_client.get_all_registration_codes(token)
        if result.success and isinstance(result.data, list):
            codes = result.data
            return format_codes_as_html_table(codes) if codes else AdminMessages.NO_CODES_FOUND
        else:
            logger.error(f"Ошибка при получении кодов: {result.detail}")
            return ErrorMessages.Codes.CODES_RETRIEVAL_ERROR
    except Exception as e:
        logger.error(f"Критическая ошибка при получении кодов: {e}", exc_info=True)
        return ErrorMessages.Codes.CODES_RETRIEVAL_ERROR


async def get_system_stats_text(token: str | None, admin_client: AdminClient) -> str:
    """Получает и форматирует текст системной статистики."""
    if not token:
        return ErrorMessages.Auth.UNAUTHORIZED
    try:
        result = await asyncio.wait_for(admin_client.get_system_stats(token), timeout=STATS_TIMEOUT)
        if result.success and isinstance(result.data, dict):
            return format_stats_message(result.data)
        else:
            return ErrorMessages.Stats.STATS_RETRIEVAL_ERROR
    except Exception as e:
        logger.error(f"Неожиданная ошибка в get_system_stats_text: {e}", exc_info=True)
        return ErrorMessages.API.UNEXPECTED_ERROR


async def _send_system_stats(
    message: Message, token: str | None, admin_client: AdminClient, edit: bool = False
) -> None:
    """Получает и отправляет (или редактирует) сообщение со статистикой."""
    response_text = await get_system_stats_text(token, admin_client)
    if edit:
        await message.edit_text(text=response_text, reply_markup=get_back_to_menu_keyboard())
    else:
        await message.answer(response_text)


async def _handle_callback_stats(
    callback: CallbackQuery, token: str | None, admin_client: AdminClient
) -> None:
    """Обрабатывает запрос статистики через callback."""

    if callback.message is None:
        logger.warning("CallbackQuery не имеет связанного сообщения.")
        await callback.answer()
        return
    await _send_system_stats(callback.message, token, admin_client, edit=True)
    await callback.answer()


async def _handle_message_stats(
    message: Message, token: str | None, admin_client: AdminClient
) -> None:
    """Обрабатывает запрос статистики через сообщение."""

    await _send_system_stats(message, token, admin_client, edit=False)


async def _handle_stats_error(
    event: Message | CallbackQuery, telegram_id: int, error: Exception
) -> None:
    """Обрабатывает ошибки при получении статистики."""
    logger.error(
        f"Ошибка в system_stats_handler для пользователя {telegram_id}: {error}", exc_info=True
    )
    error_message = ErrorMessages.Stats.STATS_RETRIEVAL_ERROR
    try:
        if isinstance(event, CallbackQuery) and event.message:
            await event.message.answer(error_message)
        elif isinstance(event, Message):
            await event.answer(error_message)
    except Exception as inner_error:
        logger.error(
            f"Не удалось отправить сообщение об ошибке пользователю {telegram_id}: {inner_error}"
        )
    finally:
        if isinstance(event, CallbackQuery):
            await event.answer()


async def get_api_status_text(system_client: SystemClient) -> str:
    """Проверяет состояние API (не требует токена)."""
    try:
        result = await system_client.health_check()
        if result.success and isinstance(result.data, dict):
            health_data = result.data
            return CommonMessages.API_STATUS_TEMPLATE.format(
                status=health_data.get("status", "N/A"),
                app=health_data.get("app", "N/A"),
                version=health_data.get("version", "N/A"),
                timestamp=health_data.get("timestamp", "N/A"),
            )
        else:
            return ErrorMessages.API.API_ERROR(detail=result.detail or "статус не 'ok'")
    except Exception as e:
        logger.error(f"Ошибка при проверке API: {e}", exc_info=True)
        return ErrorMessages.API.CONNECTION_ERROR(error=str(e))
