import asyncio
from typing import Any

import httpx
from aiogram.types import InlineKeyboardMarkup, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.admin_client import AdminClient
from bot.constants import MAX_CODES_DISPLAY, STATS_TIMEOUT
from bot.errors import ErrorMessages
from bot.handlers.keyboards import get_admin_main_keyboard
from bot.messages import AdminMessages, AdminServiceMessages
from bot.utils import format_stats_message

logger = get_logger(__name__)


def get_admin_menu() -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает текст и клавиатуру для главного меню админа."""
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
    except TimeoutError:
        logger.error(f"Таймаут при создании кода для {role.value}")
        return ErrorMessages.API.TIMEOUT_ERROR
    except httpx.RequestError as e:
        logger.error(f"Ошибка сети при создании кода для {role.value}: {e}")
        return ErrorMessages.API.CONNECTION_ERROR(error=str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании кода для {role.value}: {e}", exc_info=True)
        return ErrorMessages.Codes.CODE_CREATION_ERROR(detail=AdminServiceMessages.INTERNAL_ERROR)


def _format_codes_table(codes: list[dict[str, Any]]) -> str:
    header = AdminServiceMessages.CODE_TABLE_HEADER
    separator = "-" * len(header)
    lines = [header, separator]
    for c in codes[:MAX_CODES_DISPLAY]:
        code = c.get("code", "?")
        role = c.get("role", "?")
        status = AdminServiceMessages.USED if c.get("is_used") else AdminServiceMessages.NOT_USED
        line = f"{code:<12}{role:<12}{status:<15}"
        lines.append(line)
    table = "\n".join(lines)
    text = AdminServiceMessages.CODES_HEADER + table + AdminServiceMessages.CODES_FOOTER
    if len(codes) > MAX_CODES_DISPLAY:
        text += AdminServiceMessages.MORE_CODES.format(len(codes) - MAX_CODES_DISPLAY)
    return text


async def get_formatted_codes(telegram_id: int, admin_client: AdminClient) -> str:
    try:
        result = await admin_client.get_all_registration_codes(telegram_id)
        if result.success and isinstance(result.data, list):
            codes = result.data
            if codes:
                return _format_codes_table(codes)
            else:
                return AdminMessages.NO_CODES_FOUND
        else:
            return ErrorMessages.Codes.CODES_RETRIEVAL_ERROR
    except Exception as e:
        logger.error(f"Ошибка при получении кодов для {telegram_id}: {e}", exc_info=True)
        return ErrorMessages.Codes.CODES_RETRIEVAL_ERROR


async def get_system_stats_text(user_id: int, admin_client: AdminClient) -> str:
    """Получает системную статистику и возвращает готовый текст."""
    try:
        result = await asyncio.wait_for(
            admin_client.get_system_stats(user_id), timeout=STATS_TIMEOUT
        )
        if result.success and isinstance(result.data, dict):
            return format_stats_message(result.data)
        else:
            return ErrorMessages.Stats.STATS_RETRIEVAL_ERROR
    except TimeoutError:
        logger.error(f"Таймаут при получении системной статистики для user_id={user_id}")
        return ErrorMessages.API.TIMEOUT_ERROR
    except httpx.RequestError as e:
        logger.error(f"Ошибка сети при получении системной статистики: {e}")
        return ErrorMessages.API.CONNECTION_ERROR(error=e)
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
