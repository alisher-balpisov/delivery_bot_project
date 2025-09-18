import asyncio

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.admin_client import AdminClient
from bot.constants import STATS_TIMEOUT
from bot.errors import ErrorMessages
from bot.handlers.keyboards import get_admin_main_keyboard
from bot.messages import AdminMessages, AdminServiceMessages
from bot.utils.formatters import format_codes_as_html_table
from bot.utils.helpers import format_stats_message

logger = get_logger(__name__)


def get_admin_menu() -> tuple[str, InlineKeyboardMarkup]:
    return AdminMessages.MENU, get_admin_main_keyboard()


async def create_registration_code(
    telegram_id: int,
    admin_client: AdminClient,
    role: UserRole,
) -> str:
    try:
        result = await admin_client.create_registration_code(telegram_id, role)
        if result.success and isinstance(result.data, dict) and result.data.get("code"):
            code = result.data["code"]
            return AdminMessages.CODE_CREATED.format(role.value.upper(), code)
        else:
            error_detail = result.detail or AdminServiceMessages.CONNECTION_ERROR
            return ErrorMessages.Codes.CODE_CREATION_ERROR(detail=error_detail)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании кода для {role.value}: {e}", exc_info=True)
        return ErrorMessages.Codes.CODE_CREATION_ERROR(detail=AdminServiceMessages.INTERNAL_ERROR)


async def get_formatted_codes(telegram_id: int, admin_client: AdminClient) -> str:
    """
    Получает коды из API и передает их в форматер для генерации сообщения.
    """
    try:
        result = await admin_client.get_all_registration_codes(telegram_id)

        if result.success and isinstance(result.data, list):
            codes = result.data
            if codes:
                return format_codes_as_html_table(codes)
            else:
                return AdminMessages.NO_CODES_FOUND
        else:
            logger.error(f"Ошибка при получении кодов для {telegram_id}: {result.detail}")
            return ErrorMessages.Codes.CODES_RETRIEVAL_ERROR
    except Exception as e:
        logger.error(
            f"Критическая ошибка при получении кодов для {telegram_id}: {e}", exc_info=True
        )
        return ErrorMessages.Codes.CODES_RETRIEVAL_ERROR


async def get_system_stats_text(user_id: int, admin_client: AdminClient) -> str:
    try:
        result = await asyncio.wait_for(
            admin_client.get_system_stats(user_id), timeout=STATS_TIMEOUT
        )
        if result.success and isinstance(result.data, dict):
            return format_stats_message(result.data)
        else:
            return ErrorMessages.Stats.STATS_RETRIEVAL_ERROR
    except Exception as e:
        logger.error(f"Неожиданная ошибка в get_system_stats_text: {e}", exc_info=True)
        return ErrorMessages.API.UNEXPECTED_ERROR


async def _send_system_stats(
    message: Message, user_id: int, admin_client: AdminClient, edit: bool = False
) -> None:
    """
    Получает, форматирует и отправляет (или редактирует) сообщение со статистикой.

    Args:
        message: Объект сообщения для ответа или редактирования.
        user_id: Telegram ID пользователя, запрашивающего статистику.
        admin_client: Клиент для доступа к API администратора.
        edit: Если True, редактирует существующее сообщение, иначе отправляет новое.
    """
    response_text = await get_system_stats_text(user_id, admin_client)

    if edit:
        await message.edit_text(response_text)
    else:
        await message.answer(response_text)


async def _handle_callback_stats(
    callback: CallbackQuery, telegram_id: int, admin_client: AdminClient
) -> None:
    """
    Обрабатывает запрос статистики через callback.

    Args:
        callback: Объект callback запроса
        telegram_id: ID пользователя в Telegram
        admin_client: Клиент для API администратора
    """
    # Guard clause: проверка на отсутствие сообщения
    if callback.message is None:
        logger.warning(
            f"CallbackQuery без связанного сообщения для пользователя {telegram_id}. "
            "Возможно, сообщение было удалено или callback относится к inline сообщению."
        )
        await callback.answer()
        return

    await _send_system_stats(callback.message, telegram_id, admin_client, edit=True)
    await callback.answer()


async def _handle_message_stats(
    message: Message, telegram_id: int, admin_client: AdminClient
) -> None:
    """
    Обрабатывает запрос статистики через сообщение.

    Args:
        message: Объект сообщения
        telegram_id: ID пользователя в Telegram
        admin_client: Клиент для API администратора
    """
    await _send_system_stats(message, telegram_id, admin_client, edit=False)


async def _handle_stats_error(
    event: Message | CallbackQuery, telegram_id: int, error: Exception
) -> None:
    """
    Обрабатывает ошибки при получении статистики.

    Args:
        event: Объект события (Message или CallbackQuery)
        telegram_id: ID пользователя в Telegram
        error: Исключение, которое произошло
    """
    from bot.errors import ErrorMessages

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
        # Гарантированное выполнение для callback
        if isinstance(event, CallbackQuery):
            await event.answer()
