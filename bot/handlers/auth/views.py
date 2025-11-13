from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.auth_client import AuthClient
from bot.clients.users_client import UsersClient
from bot.dto import UserDTO
from bot.filters.filters import IsAuthenticatedFilter
from bot.handlers.states import RegistrationStates
from bot.messages import AuthMessages, AuthServiceMessages
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

from . import service

logger = get_logger(__name__)

auth_router = Router(name="auth_handlers")


@auth_router.message(Command("start"))
async def start_handler(
    message: Message,
    state: FSMContext,
    user: UserDTO,
    auth_client: AuthClient,
    users_client: UsersClient,
    user_storage: UserDataStorage,
) -> None:
    """
    Обработчик команды /start.

    Логика:
    1. Проверяет наличие валидного токена в Redis
    2. Если успех - показываем приветствие
    3. Если токена нет - предлагаем регистрацию
    """
    telegram_id = message.from_user.id
    logger.info(f"Команда /start от пользователя {telegram_id}")

    # Создаем TokenManager
    token_manager = TokenManager(auth_client, user_storage)

    # Проверяем наличие валидного токена
    token = await token_manager.get_token(telegram_id)

    # Если токен есть - пользователь зарегистрирован
    if token:
        logger.info(f"Пользователь {telegram_id} авторизован")

        # Получаем профиль
        user_profile = await service.get_user_profile_by_token(token, users_client)

        if user_profile:
            await service.handle_authenticated_user(
                message,
                state,
                user_profile,
                telegram_id,
            )
            return

    # Токена нет - проверяем статус через login
    token_result = await auth_client.login(telegram_id)
    status_code = token_result.status_code

    # 403 - регистрация не завершена (пользователь существует, но не ввел код)
    if status_code == 403:
        logger.info(f"Пользователь {telegram_id} не завершил регистрацию")
        await state.set_state(RegistrationStates.waiting_for_code)
        await message.answer(
            "⚠️ Вы начали регистрацию, но не завершили её.\n\n" + AuthMessages.ENTER_CODE
        )
        return

    # 401 или другой код - совсем новый пользователь
    logger.info(f"Новый пользователь {telegram_id}, предлагаем регистрацию")
    await state.clear()
    await message.answer(AuthMessages.WELCOME_NEW_USER)


@auth_router.message(Command("register"))
async def register_handler(
    message: Message,
    state: FSMContext,
    user: UserDTO,
) -> None:
    """Начинает процесс регистрации."""
    if user.role != UserRole.GUEST:
        await message.answer(AuthMessages.ALREADY_REGISTERED)
    else:
        await state.set_state(RegistrationStates.waiting_for_code)
        await message.answer(AuthMessages.ENTER_CODE)


@auth_router.message(RegistrationStates.waiting_for_code)
async def register_code_handler(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
) -> None:
    """Обрабатывает введенный код регистрации и получает токен."""
    telegram_id = message.from_user.id
    code = (message.text or "").strip()

    # Базовая валидация кода
    if not code:
        await message.answer("❌ Код не может быть пустым. Попробуйте еще раз:")
        return

    if len(code) < 4 or len(code) > 20:
        await message.answer("❌ Код должен быть от 4 до 20 символов. Попробуйте еще раз:")
        return

    loading_msg = await message.answer(AuthMessages.CHECKING_CODE)

    try:
        result = await auth_client.auth_by_code(telegram_id, code, message.from_user.username)

        if result.success and isinstance(result.data, dict):
            # Успешная регистрация
            await service.handle_registration_success(
                message, state, result.data, telegram_id, auth_client, user_storage
            )
        else:
            # Обработка ошибок
            await service.handle_registration_failure(message, state, result.detail)

    except Exception as e:
        logger.error(
            AuthServiceMessages.REGISTRATION_CRITICAL_ERROR.format(telegram_id, e),
            exc_info=True,
        )
        await state.clear()
        await message.answer(AuthServiceMessages.CRITICAL_REGISTRATION_ERROR)
    finally:
        await loading_msg.delete()


@auth_router.message(Command("me"), IsAuthenticatedFilter())
async def user_stats_handler(
    message: Message,
    auth_client: AuthClient,
    users_client: UsersClient,
    user_storage: UserDataStorage,
):
    """Получить статистику пользователя (требует авторизации)."""
    # Создаем TokenManager
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(message.from_user.id)

    response_text = await service.get_user_stats_text(token, users_client)
    await message.answer(response_text)


@auth_router.message(Command("logout"), IsAuthenticatedFilter())
async def logout_handler(
    message: Message,
    state: FSMContext,
    user: UserDTO,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Обработчик команды /logout."""
    # Создаем TokenManager и инвалидируем токены
    token_manager = TokenManager(auth_client, user_storage)
    await token_manager.invalidate_token(user.telegram_id)

    # Очищаем FSM state
    await state.clear()

    # Удаляем все данные пользователя из Redis
    await user_storage.delete_user_data(user.telegram_id)

    await message.answer(AuthMessages.LOGOUT_SUCCESS)
