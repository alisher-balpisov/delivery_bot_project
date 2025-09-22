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
    Получает JWT токен для пользователя и сохраняет его.
    """
    telegram_id = message.from_user.id
    token_result = await auth_client.get_token(telegram_id)

    if token_result.success and isinstance(token_result.data, dict):
        token = token_result.data.get("access_token")
        await state.update_data(jwt_token=token)
        logger.info(f"JWT токен для пользователя {telegram_id} получен и кэширован")

        # Теперь, когда токен есть, получаем профиль
        user_profile_result = await service.get_user_profile_by_token(token, users_client)
        if user_profile_result:
            await service.handle_authenticated_user(
                message,
                state,
                user_profile_result,
                telegram_id,
            )
            return

    # Если токен не получен или профиль не загружен
    await state.clear()
    guest_user = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)
    await state.update_data(user=guest_user.model_dump())
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
) -> None:
    """Обрабатывает введенный код регистрации и получает токен."""
    telegram_id = message.from_user.id
    code = (message.text or "").strip()
    loading_msg = await message.answer(AuthMessages.CHECKING_CODE)

    try:
        result = await auth_client.auth_by_code(telegram_id, code)
        if result.success and isinstance(result.data, dict):
            # Успешная регистрация, получаем токен из ответа
            await service.handle_registration_success(message, state, result.data, telegram_id)
        else:
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
