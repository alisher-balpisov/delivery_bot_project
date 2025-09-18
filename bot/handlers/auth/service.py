from typing import Any

import httpx
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.users_client import UsersClient
from bot.constants import ROLE_EMOJI_MAP
from bot.dto import UserDTO
from bot.errors import ErrorMessages
from bot.messages import AuthMessages, AuthServiceMessages
from bot.utils.helpers import parse_user_role

logger = get_logger(__name__)


async def _update_user_state(state: FSMContext, user_info: dict, telegram_id: int) -> UserDTO:
    """Обновляет состояние FSM данными пользователя из словаря и возвращает DTO."""
    role = parse_user_role(user_info.get("role", UserRole.GUEST.value))
    user_dto = UserDTO(
        user_id=user_info.get("id"),
        name=user_info.get("name", ""),
        telegram_id=telegram_id,
        role=role,
    )
    await state.update_data(user=user_dto.model_dump())
    logger.info(AuthServiceMessages.STATE_UPDATED.format(user_dto.telegram_id))
    return user_dto


async def handle_registration_success(
    message: Message, state: FSMContext, user_info: dict, telegram_id: int
) -> None:
    """Обрабатывает успешную регистрацию."""
    user_dto = await _update_user_state(state, user_info, telegram_id)
    role_emoji = ROLE_EMOJI_MAP.get(user_dto.role, "")
    text = AuthMessages.SUCCESS.format(role_emoji)
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.clear()


async def handle_registration_failure(
    message: Message, state: FSMContext, result_detail: dict | str | None
) -> None:
    """
    Обрабатывает неудачную регистрацию на основе данных из поля 'detail' ответа API.
    """
    # Если detail - это словарь, ищем в нем информацию о блокировке или попытках
    if isinstance(result_detail, dict):
        if result_detail.get("blocked"):
            await message.answer(AuthMessages.BLOCKED)
            # При блокировке состояние не очищаем, чтобы пользователь не мог сразу попробовать снова
            return
        elif "attempts_left" in result_detail:
            attempts = result_detail.get("attempts_left", 0)
            await message.answer(AuthMessages.INVALID_CODE_ATTEMPTS.format(attempts))
            return

    # Если detail - строка или словарь без нужных ключей, показываем общую ошибку
    logger.warning(
        f"Регистрация не удалась. Detail от API: {result_detail} для {message.from_user.id}"
    )
    await message.answer(AuthMessages.INVALID_CODE)


async def handle_authenticated_user(
    message: Message,
    state: FSMContext,
    user_profile: dict[str, Any],
) -> None:
    """Обрабатывает авторизованного пользователя: отправляет приветствие и обновляет состояние."""
    role = parse_user_role(user_profile.get("role", UserRole.GUEST.value))

    if role == UserRole.ADMIN:
        await message.answer(AuthMessages.WELCOME_ADMIN)
    else:
        await message.answer(AuthMessages.WELCOME_AUTHENTICATED)

    telegram_id = user_profile.get("telegram_id") or message.from_user.id
    await _update_user_state(state, user_profile, telegram_id)


async def get_user_stats_text(telegram_id: int, users_client: UsersClient) -> str:
    """Получает и форматирует статистику пользователя."""
    try:
        user_profile_result = await users_client.get_user_profile(telegram_id)

        if user_profile_result.success and isinstance(user_profile_result.data, dict):
            user_info = user_profile_result.data
            user_dto = UserDTO(
                user_id=user_info.get("id"),
                telegram_id=user_info.get("telegram_id"),
                name=user_info.get("name"),
                role=parse_user_role(user_info.get("role", "guest")),
            )
            status = (
                AuthServiceMessages.ACTIVE
                if user_info.get("is_active")
                else AuthServiceMessages.DEACTIVATED
            )
            is_blocked = (
                AuthServiceMessages.YES if user_info.get("is_blocked") else AuthServiceMessages.NO
            )

            return AuthMessages.ME_STATS_TEMPLATE.format(
                id=user_dto.user_id or "N/A",
                name=user_dto.name or AuthServiceMessages.NOT_SPECIFIED,
                emoji=ROLE_EMOJI_MAP.get(user_dto.role, "👤"),
                role=user_dto.role.value.upper(),
                telegram_id=user_dto.telegram_id,
                status=status,
                is_blocked=is_blocked,
            )
        else:
            detail = user_profile_result.detail or AuthServiceMessages.UNKNOWN_ERROR
            return ErrorMessages.Stats.STATS_ERROR(detail=detail)

    except httpx.RequestError as e:
        return ErrorMessages.API.CONNECTION_ERROR(error=e)
    except Exception as e:
        logger.error(AuthServiceMessages.UNEXPECTED_ERROR.format(e), exc_info=True)
        return ErrorMessages.API.UNEXPECTED_ERROR
