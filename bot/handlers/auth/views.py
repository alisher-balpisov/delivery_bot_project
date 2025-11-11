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
from icecream import ic

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
) -> None:
    """
    Обработчик команды /start.

    Логика:
    1. Пытается получить JWT токен через login()
    2. Если успех (200) - пользователь зарегистрирован, показываем приветствие
    3. Если 403 (регистрация не завершена) - предлагаем ввести код
    4. Если 401 (пользователь не найден) - предлагаем регистрацию
    5. Если другая ошибка - показываем как гостя
    """
    telegram_id = message.from_user.id
    logger.info(f"Команда /start от пользователя {telegram_id}")

    token_result = await auth_client.login(telegram_id)
    ic(token_result)

    # Успешная авторизация - пользователь уже зарегистрирован
    if token_result.success and isinstance(token_result.data, dict):
        token = token_result.data.get("access_token")
        await state.update_data(jwt_token=token)
        logger.info(f"JWT токен для пользователя {telegram_id} получен и кэширован")

        # Получаем профиль пользователя
        user_profile = await service.get_user_profile_by_token(token, users_client)
        ic(user_profile)

        if user_profile:
            await service.handle_authenticated_user(
                message,
                state,
                user_profile,
                telegram_id,
            )
            return

    # Обработка ошибок авторизации
    status_code = token_result.status_code

    # 403 - регистрация не завершена (пользователь существует, но не ввел код)
    if status_code == 403:
        logger.info(f"Пользователь {telegram_id} не завершил регистрацию")
        await state.set_state(RegistrationStates.waiting_for_code)
        await message.answer(
            "⚠️ Вы начали регистрацию, но не завершили её.\n\n" + AuthMessages.ENTER_CODE
        )
        return

    # 401 - пользователь не найден (совсем новый пользователь)
    if status_code == 401:
        logger.info(f"Новый пользователь {telegram_id}, предлагаем регистрацию")
        await state.clear()
        guest_user = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)
        await state.update_data(user=guest_user.model_dump())
        await message.answer(AuthMessages.WELCOME_NEW_USER)
        return

    # Другие ошибки - показываем как гостя
    logger.warning(
        f"Неожиданный статус {status_code} при /start для {telegram_id}: {token_result.detail}"
    )
    await state.clear()
    guest_user = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)
    await state.update_data(user=guest_user.model_dump())
    await message.answer("⚠️ Произошла ошибка при авторизации.\n\n" + AuthMessages.WELCOME_NEW_USER)


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
            # Успешная регистрация, получаем токен из ответа
            await service.handle_registration_success(message, state, result.data, telegram_id)
        else:
            # Обработка различных ошибок
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
async def user_stats_handler(message: Message, state: FSMContext, users_client: UsersClient):
    """Получить статистику пользователя (требует авторизации)."""
    data = await state.get_data()
    token = data.get("jwt_token")
    response_text = await service.get_user_stats_text(token, users_client)
    await message.answer(response_text)


@auth_router.message(Command("logout"), IsAuthenticatedFilter())
async def logout_handler(message: Message, state: FSMContext, user: UserDTO):
    """Обработчик команды /logout."""
    await state.clear()
    guest_dto = UserDTO(telegram_id=user.telegram_id, role=UserRole.GUEST)
    await state.update_data(user=guest_dto.model_dump())
    await message.answer(AuthMessages.LOGOUT_SUCCESS)
