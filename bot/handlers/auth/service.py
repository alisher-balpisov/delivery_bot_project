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
from bot.exceptions import ErrorMessages
from bot.messages import AuthMessages, AuthServiceMessages
from bot.utils.helpers import parse_user_role
from icecream import ic

logger = get_logger(__name__)


async def _update_user_state_from_profile(
    state: FSMContext,
    user_profile: dict,
    telegram_id: int,
) -> UserDTO | None:
    """Обновляет состояние FSM из данных профиля и возвращает DTO."""
    if not user_profile:
        return None

    role = parse_user_role(user_profile.get("role", UserRole.GUEST.value))
    user_dto = UserDTO(
        user_id=user_profile.get("id"),
        telegram_id=telegram_id,
        name=user_profile.get("name", ""),
        role=role,
    )
    # Сохраняем только DTO пользователя, токен уже должен быть в state
    await state.update_data(user=user_dto.model_dump())
    logger.info(AuthServiceMessages.STATE_UPDATED.format(user_dto.telegram_id))
    return user_dto


async def handle_registration_success(
    message: Message, state: FSMContext, response_data: dict, telegram_id: int
) -> None:
    """Обрабатывает успешную регистрацию, сохраняет токен и обновляет DTO."""
    access_token = response_data.get("access_token")
    user_info = response_data.get("user", {})

    if not access_token:
        logger.error(f"В успешном ответе регистрации для {telegram_id} отсутствует access_token")
        await message.answer(AuthServiceMessages.GENERIC_ERROR)
        await state.clear()
        return

    # Сохраняем токен в FSM
    await state.update_data(jwt_token=access_token)
    logger.info(f"JWT токен для пользователя {telegram_id} получен и кэширован после регистрации.")

    # Обновляем DTO пользователя
    user_dto = await _update_user_state_from_profile(state, user_info, telegram_id)
    if not user_dto:
        await message.answer(AuthServiceMessages.GENERIC_ERROR)
        return

    # Определяем приветственное сообщение в зависимости от роли
    if user_dto.role == UserRole.ADMIN:
        text = AuthMessages.WELCOME_ADMIN
    else:
        text = AuthMessages.SUCCESS + "\n\n" + AuthMessages.WELCOME_AUTHENTICATED

    await message.answer(text, parse_mode=ParseMode.HTML)

    # Очищаем состояние регистрации и сохраняем только нужные данные
    await state.clear()
    await state.update_data({"user": user_dto.model_dump(), "jwt_token": access_token})


async def handle_registration_failure(
    message: Message, state: FSMContext, result_detail: dict | str | None
) -> None:
    """
    Обрабатывает неудачную регистрацию.

    Возможные причины:
    - Неверный код
    - Превышен лимит попыток (блокировка)
    - Код уже использован
    - Код истек
    """
    # Если detail - словарь с подробностями
    if isinstance(result_detail, dict):
        # Проверяем блокировку
        if result_detail.get("blocked"):
            await message.answer(AuthMessages.BLOCKED)
            await state.clear()
            return

        # Проверяем оставшиеся попытки
        attempts_left = result_detail.get("attempts_left")
        if attempts_left is not None:
            await message.answer(AuthMessages.INVALID_CODE_ATTEMPTS.format(attempts_left))
            return

    # Если detail - строка с описанием ошибки
    if isinstance(result_detail, str):
        # Проверяем на специфичные сообщения об ошибках
        detail_lower = result_detail.lower()

        if "превышен" in detail_lower or "заблокирован" in detail_lower:
            await message.answer(AuthMessages.BLOCKED)
            await state.clear()
            return

        if "попыт" in detail_lower:
            # Пытаемся извлечь количество попыток из сообщения
            import re

            match = re.search(r"(\d+)", result_detail)
            if match:
                attempts = int(match.group(1))
                await message.answer(AuthMessages.INVALID_CODE_ATTEMPTS.format(attempts))
                return

    # Общая ошибка - неверный код
    logger.warning(
        f"Регистрация не удалась. Detail от API: {result_detail} для {message.from_user.id}"
    )
    await message.answer(
        AuthMessages.INVALID_CODE
        + "\n\nПопробуйте еще раз или получите новый код у администратора."
    )


async def handle_authenticated_user(
    message: Message,
    state: FSMContext,
    user_profile: dict[str, Any],
    telegram_id: int,
) -> None:
    """Обрабатывает авторизованного пользователя при /start."""
    role = parse_user_role(user_profile.get("role", UserRole.GUEST.value))

    # Обновляем состояние пользователя
    await _update_user_state_from_profile(state, user_profile, telegram_id)

    # Отправляем приветствие в зависимости от роли
    if role == UserRole.ADMIN:
        await message.answer(AuthMessages.WELCOME_ADMIN)
    elif role == UserRole.GUEST:
        await message.answer(AuthMessages.WELCOME_NEW_USER)
    else:
        await message.answer(AuthMessages.WELCOME_AUTHENTICATED)


async def get_user_profile_by_token(token: str, users_client: UsersClient) -> dict | None:
    """Получает профиль пользователя, используя JWT токен."""
    if not token:
        return None

    try:
        profile_result = await users_client.get_user_profile(token)
        ic(profile_result)

        if profile_result.success and isinstance(profile_result.data, dict):
            return profile_result.data

        logger.warning(
            f"Не удалось получить профиль пользователя с помощью токена: "
            f"статус {profile_result.status_code}, detail: {profile_result.detail}"
        )
        return None

    except Exception as e:
        logger.error(f"Ошибка при получении профиля по токену: {e}", exc_info=True)
        return None


async def get_user_stats_text(token: str | None, users_client: UsersClient) -> str:
    """Получает и форматирует статистику пользователя по токену."""
    if not token:
        return ErrorMessages.Auth.UNAUTHORIZED

    try:
        user_profile_result = await users_client.get_user_profile(token)

        if not user_profile_result.success:
            detail = user_profile_result.detail or AuthServiceMessages.UNKNOWN_ERROR
            return ErrorMessages.Stats.STATS_ERROR(detail=detail)

        if not isinstance(user_profile_result.data, dict):
            return ErrorMessages.Stats.STATS_ERROR(detail="Неверный формат данных")

        user_info = user_profile_result.data
        user_dto = UserDTO(
            user_id=user_info.get("id"),
            telegram_id=user_info.get("telegram_id"),
            name=user_info.get("name"),
            role=parse_user_role(user_info.get("role", UserRole.GUEST.value)),
        )

        # Определяем статус аккаунта
        status = (
            AuthServiceMessages.DEACTIVATED
            if user_info.get("is_deleted")
            else AuthServiceMessages.ACTIVE
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

    except httpx.RequestError as e:
        logger.error(f"Ошибка сети при получении статистики: {e}")
        return ErrorMessages.API.CONNECTION_ERROR(error=str(e))
    except Exception as e:
        logger.error(AuthServiceMessages.UNEXPECTED_ERROR.format(e), exc_info=True)
        return ErrorMessages.API.UNEXPECTED_ERROR
