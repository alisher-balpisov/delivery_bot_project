import asyncio
from typing import Any

import httpx
from aiogram.types import InlineKeyboardMarkup
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients import client_manager
from bot.constants import STATS_TIMEOUT, ErrorMessages
from bot.handlers.keyboards import get_admin_main_keyboard
from bot.messages import AdminMessages, AdminServiceMessages
from bot.utils import format_stats_message

logger = get_logger(__name__)


def get_admin_menu() -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает текст и клавиатуру для главного меню админа."""
    return AdminMessages.MENU, get_admin_main_keyboard()


async def create_registration_code(telegram_id: int, role: UserRole) -> str:
    """Создает код регистрации и возвращает отформатированный ответ."""
    if role not in [UserRole.SHOP, UserRole.COURIER]:
        return ErrorMessages.UserData.INVALID_ROLE

    try:
        result = await client_manager.admin.create_registration_code(telegram_id, role)
        if result and result.get("code"):
            code = result["code"]
            return AdminMessages.CODE_CREATED.format(role.value.upper(), code)

        detail = (
            result.get("detail", AdminServiceMessages.UNKNOWN_ERROR)
            if result
            else AdminServiceMessages.CONNECTION_ERROR
        )
        return ErrorMessages.Codes.CODE_CREATION_ERROR(detail=detail)
    except Exception as e:
        logger.error(f"Ошибка при создании кода для {role.value}: {e}", exc_info=True)
        return ErrorMessages.Codes.CODE_CREATION_ERROR(detail=AdminServiceMessages.INTERNAL_ERROR)


def _format_codes_table(codes: list[dict[str, Any]]) -> str:
    """Форматирует список кодов в текстовую таблицу."""
    header = AdminServiceMessages.CODE_TABLE_HEADER
    separator = "-" * len(header)
    lines = [header, separator]

    for c in codes[:10]:
        code = c.get("code", "?")
        role = c.get("role", "?")
        status = AdminServiceMessages.USED if c.get("is_used") else AdminServiceMessages.NOT_USED
        line = f"{code:<12}{role:<12}{status:<15}"
        lines.append(line)

    table = "\n".join(lines)
    text = AdminServiceMessages.CODES_HEADER + table + AdminServiceMessages.CODES_FOOTER
    if len(codes) > 10:
        text += AdminServiceMessages.MORE_CODES.format(len(codes) - 10)
    return text


async def get_formatted_codes(telegram_id: int) -> str:
    """Получает и форматирует список кодов регистрации."""
    try:
        codes = await client_manager.admin.get_all_registration_codes(telegram_id)
        if codes and isinstance(codes, list):
            return _format_codes_table(codes)
        elif not codes:
            return AdminMessages.NO_CODES_FOUND
        else:
            return ErrorMessages.Codes.CODES_RETRIEVAL_ERROR
    except Exception as e:
        logger.error(f"Ошибка при получении кодов для {telegram_id}: {e}", exc_info=True)
        return ErrorMessages.Codes.CODES_RETRIEVAL_ERROR


async def get_system_stats_text(user_id: int) -> str:
    """Получает системную статистику и возвращает готовый текст."""
    try:
        stats = await asyncio.wait_for(
            client_manager.admin.get_system_stats(user_id), timeout=STATS_TIMEOUT
        )
        if not stats:
            return ErrorMessages.Stats.STATS_RETRIEVAL_ERROR
        return format_stats_message(stats)
    except TimeoutError:
        logger.error(f"Timeout при получении системной статистики для user_id={user_id}")
        return ErrorMessages.API.TIMEOUT_ERROR
    except httpx.RequestError as e:
        logger.error(f"Ошибка сети при получении системной статистики: {e}")
        return ErrorMessages.API.CONNECTION_ERROR(error=e)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при get_system_stats_text: {e}", exc_info=True)
        return ErrorMessages.API.UNEXPECTED_ERROR

