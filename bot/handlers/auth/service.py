from typing import Any

import httpx
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients import client_manager
from bot.constants import ROLE_EMOJI_MAP, ErrorMessages
from bot.messages import AuthMessages, AuthServiceMessages

logger = get_logger(__name__)


def _parse_user_role(role_str: str) -> UserRole:
    """Парсит строку роли в UserRole enum, возвращает GUEST при ошибке."""
    try:
        return UserRole(role_str)
    except ValueError:
        logger.warning(AuthServiceMessages.UNKNOWN_ROLE.format(role_str))
        return UserRole.GUEST


async def _update_user_state(state: FSMContext, role: UserRole, user_id: int) -> None:
    """Обновляет состояние FSM с данными пользователя."""
    await state.update_data(role=role, user_id=user_id)


async def _handle_registration_success(
    message: Message, state: FSMContext, user_info: dict
) -> None:
    """Обрабатывает успешную регистрацию."""
    role_enum = _parse_user_role(user_info.get("role", UserRole.GUEST.value))
    await _update_user_state(state, role_enum, user_info.get("id"))

    role_emoji = ROLE_EMOJI_MAP.get(role_enum, ROLE_EMOJI_MAP[UserRole.GUEST])
    role_bold = hbold(role_enum.value.upper())
    text = AuthMessages.SUCCESS.format(role_emoji, role_bold)
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.clear()


async def _handle_registration_failure(message: Message, state: FSMContext, result: dict) -> None:
    """Обрабатывает неудачную регистрацию на основе результата."""
    if result.get("blocked"):
        await message.answer(AuthMessages.BLOCKED)
        await state.clear()
    elif "attempts_left" in result:
        attempts = result.get("attempts_left", 0)
        await message.answer(AuthMessages.INVALID_CODE_ATTEMPTS.format(attempts))
    else:
        await message.answer(AuthMessages.INVALID_CODE)


async def handle_authenticated_user(
    message: Message,
    state: FSMContext,
    user_data: dict[str, Any],
    telegram_id: int,
) -> None:
    """Обрабатывает авторизованного пользователя: отправляет приветствие и обновляет состояние, если необходимо."""
    role = user_data.get("role", "unknown")

    if role == UserRole.ADMIN:
        await message.answer(AuthMessages.WELCOME_ADMIN)
    else:
        await message.answer(AuthMessages.WELCOME_AUTHENTICATED)

    state_data = await state.get_data()
    if not state_data or state_data.get("role") != role:
        await state.update_data(
            role=role,
            user_id=user_data.get("id"),
            name=user_data.get("name", ""),
            telegram_id=telegram_id,
        )
        logger.info(AuthServiceMessages.STATE_UPDATED.format(telegram_id))


from typing import Any

import httpx
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients import client_manager
from bot.constants import ROLE_EMOJI_MAP, ErrorMessages
from bot.messages import AuthMessages, AuthServiceMessages
from bot.utils import parse_user_role

logger = get_logger(__name__)


async def _update_user_state(state: FSMContext, role: UserRole, user_id: int) -> None:
    """Обновляет состояние FSM с данными пользователя."""
    await state.update_data(role=role, user_id=user_id)


async def _handle_registration_success(
    message: Message,
    state: FSMContext,
    user_info: dict
) -> None:
    """Обрабатывает успешную регистрацию."""
    role_enum = parse_user_role(user_info.get("role", UserRole.GUEST.value))
    await _update_user_state(state, role_enum, user_info.get("id"))

    role_emoji = ROLE_EMOJI_MAP.get(role_enum, ROLE_EMOJI_MAP[UserRole.GUEST])
    role_bold = hbold(role_enum.value.upper())
    text = AuthMessages.SUCCESS.format(role_emoji, role_bold)
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.clear()


async def _handle_registration_failure(message: Message, state: FSMContext, result: dict) -> None:
    """Обрабатывает неудачную регистрацию на основе результата."""
    if result.get("blocked"):
        await message.answer(AuthMessages.BLOCKED)
        await state.clear()
    elif "attempts_left" in result:
        attempts = result.get("attempts_left", 0)
        await message.answer(AuthMessages.INVALID_CODE_ATTEMPTS.format(attempts))
    else:
        await message.answer(AuthMessages.INVALID_CODE)


async def handle_authenticated_user(
    message: Message,
    state: FSMContext,
    user_data: dict[str, Any],
    telegram_id: int,
) -> None:
    """Обрабатывает авторизованного пользователя: отправляет приветствие и обновляет состояние, если необходимо."""
    role = user_data.get("role", "unknown")

    if role == UserRole.ADMIN:
        await message.answer(AuthMessages.WELCOME_ADMIN)
    else:
        await message.answer(AuthMessages.WELCOME_AUTHENTICATED)

    state_data = await state.get_data()
    if not state_data or state_data.get("role") != role:
        await state.update_data(
            role=role,
            user_id=user_data.get("id"),
            name=user_data.get("name", ""),
            telegram_id=telegram_id,
        )
        logger.info(AuthServiceMessages.STATE_UPDATED.format(telegram_id))


async def get_user_stats_text(telegram_id: int) -> str:
    """Получает и форматирует статистику пользователя."""
    try:
        user_info = await client_manager.users.get_user_profile(telegram_id)
        if not (user_info and user_info.get("success") is not False):
            return ErrorMessages.Stats.STATS_ERROR(
                detail=user_info.get("detail", AuthServiceMessages.UNKNOWN_ERROR)
            )

        role_enum = parse_user_role(user_info.get("role", "guest"))
        status = (
            AuthServiceMessages.ACTIVE
            if user_info.get("is_active", True)
            else AuthServiceMessages.DEACTIVATED
        )
        is_blocked = (
            AuthServiceMessages.YES
            if user_info.get("is_blocked", False)
            else AuthServiceMessages.NO
        )
        return AuthMessages.ME_STATS_TEMPLATE.format(
            id=user_info.get("id", "N/A"),
            name=user_info.get("name", AuthServiceMessages.NOT_SPECIFIED),
            emoji=ROLE_EMOJI_MAP.get(role_enum, ""),
            role=role_enum.value.upper(),
            telegram_id=user_info.get("telegram_id", "N/A"),
            status=status,
            is_blocked=is_blocked,
        )
    except httpx.RequestError as e:
        return ErrorMessages.API.CONNECTION_ERROR(error=e)
    except Exception as e:
        logger.error(AuthServiceMessages.UNEXPECTED_ERROR.format(e), exc_info=True)
        return ErrorMessages.API.UNEXPECTED_ERROR
