from typing import Any

import httpx
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.auth_client import AuthClient
from bot.clients.users_client import UsersClient
from bot.constants import ROLE_EMOJI_MAP
from bot.dto import UserDTO
from bot.exceptions import ErrorMessages
from bot.messages import AuthMessages, AuthServiceMessages
from bot.redis_storage import UserCacheData, UserDataStorage
from bot.utils.helpers import parse_user_role
from bot.utils.token_manager import TokenManager

logger = get_logger(__name__)


async def handle_registration_success(
    message: Message,
    state: FSMContext,
    response_data: dict,
    telegram_id: int,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
) -> None:
    """
    Обрабатывает успешную регистрацию.

    Изменения:
    - Использует TokenManager для сохранения токенов
    - Сохраняет данные в Redis через storage
    - Убрана зависимость от FSM для хранения токенов
    """
    user_info = response_data.get("user", {})

    if not response_data.get("access_token"):
        logger.error(f"В успешном ответе регистрации для {telegram_id} отсутствует access_token")
        await message.answer(AuthServiceMessages.GENERIC_ERROR)
        await state.clear()
        return

    # Создаем TokenManager
    token_manager = TokenManager(auth_client, user_storage)

    # Создаем объект данных пользователя
    user_data = UserCacheData(
        user_id=user_info.get("id"),
        telegram_id=telegram_id,
        name=user_info.get("name"),
        role=parse_user_role(user_info.get("role")),
        username=message.from_user.username,
    )

    # Сохраняем токены и данные пользователя
    await token_manager.save_token_from_response(response_data, telegram_id, user_data)

    logger.info(f"Пользователь {telegram_id} успешно зарегистрирован")

    # Определяем приветственное сообщение
    role = user_data.role
    if role == UserRole.ADMIN:
        text = AuthMessages.WELCOME_ADMIN
    else:
        text = AuthMessages.SUCCESS + "\n\n" + AuthMessages.WELCOME_AUTHENTICATED

    await message.answer(text, parse_mode=ParseMode.HTML)

    # Очищаем FSM state
    await state.clear()


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

    # Отправляем приветствие в зависимости от роли
    if role == UserRole.ADMIN:
        await message.answer(AuthMessages.WELCOME_ADMIN)
    elif role == UserRole.GUEST:
        await message.answer(AuthMessages.WELCOME_NEW_USER)
    else:
        await message.answer(AuthMessages.WELCOME_AUTHENTICATED)


async def get_user_profile_by_token(token: str, users_client: UsersClient) -> dict | None:
    """
    Получает профиль пользователя используя JWT токен.

    Изменения:
    - Добавлено кэширование профиля (можно расширить в будущем)
    """
    if not token:
        return None

    try:
        profile_result = await users_client.get_user_profile(token)

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
