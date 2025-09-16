from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.auth_client import AuthClient
from bot.clients.users_client import UsersClient
from bot.dto import UserDTO
from bot.errors import ErrorMessages
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
) -> None:
    """Обработчик команды /start."""
    if user.role != UserRole.GUEST:
        user_profile_data = {
            "id": user.user_id,
            "telegram_id": user.telegram_id,
            "name": user.name,
            "role": user.role.value,
        }
        await service.handle_authenticated_user(message, state, user_profile_data)
    else:
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
    """Обрабатывает введенный код регистрации."""
    telegram_id = message.from_user.id
    code = (message.text or "").strip()
    loading_msg = await message.answer(AuthMessages.CHECKING_CODE)

    try:
        result = await auth_client.auth_by_code(telegram_id, code)
        await loading_msg.delete()

        if result.success and isinstance(result.data, dict) and result.data.get("success"):
            await service.handle_registration_success(message, state, result.data.get("user", {}))
        else:
            # result.data может содержать детали ошибки, такие как attempts_left
            await service.handle_registration_failure(message, state, result.data)
    except Exception as e:
        await loading_msg.delete()
        logger.error(
            AuthServiceMessages.REGISTRATION_CRITICAL_ERROR.format(telegram_id, e),
            exc_info=True,
        )
        await state.clear()
        await message.answer(AuthServiceMessages.CRITICAL_REGISTRATION_ERROR)


@auth_router.message(Command("me"))
async def user_stats_handler(message: Message, user: UserDTO, users_client: UsersClient):
    """Получить статистику пользователя (требует авторизации)."""
    if user.role == UserRole.GUEST:
        await message.answer(ErrorMessages.Auth.FORBIDDEN)
        return

    await message.answer(AuthMessages.ME_LOADING)
    response_text = await service.get_user_stats_text(user.telegram_id, users_client)
    await message.answer(response_text)


@auth_router.message(Command("logout"))
async def logout_handler(message: Message, state: FSMContext, user: UserDTO):
    """Обработчик команды /logout."""
    if user.role == UserRole.GUEST:
        await message.answer(AuthMessages.NOT_LOGGED_IN)
        return

    await state.clear()
    # Установим дефолтного пользователя-гостя после выхода
    guest_dto = UserDTO(telegram_id=user.telegram_id, role=UserRole.GUEST)
    await state.update_data(user=guest_dto.model_dump())
    await message.answer(AuthMessages.LOGOUT_SUCCESS)
