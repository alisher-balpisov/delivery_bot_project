from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients import client_manager
from bot.constants import ErrorMessages
from bot.handlers.states import RegistrationStates
from bot.messages import AuthMessages, AuthServiceMessages
from bot.utils import parse_user_role

from . import service

logger = get_logger(__name__)

auth_router = Router(name="auth_handlers")


@auth_router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start."""
    telegram_id = message.from_user.id
    try:
        user_data = await client_manager.users.get_user_profile(telegram_id)
        if user_data:
            await service.handle_authenticated_user(message, state, user_data, telegram_id)
        else:
            await message.answer(AuthMessages.WELCOME_NEW_USER)
    except Exception as e:
        logger.error(AuthServiceMessages.START_COMMAND_ERROR.format(telegram_id, e), exc_info=True)
        await message.answer(AuthServiceMessages.GENERIC_ERROR)


@auth_router.message(Command("register"))
async def register_handler(message: Message, state: FSMContext) -> None:
    """Начинает процесс регистрации."""
    telegram_id = message.from_user.id
    user_profile = await client_manager.users.get_user_profile(telegram_id)

    if not user_profile or user_profile.get("success") is False:
        await state.set_state(RegistrationStates.waiting_for_code)
        await message.answer(AuthMessages.ENTER_CODE)
    else:
        # Эта логика осталась здесь, так как она простая и тесно связана с view
        role = parse_user_role(user_profile.get("role", UserRole.GUEST.value))
        await message.answer(AuthMessages.ALREADY_REGISTERED.format(f"({role.value})"))
        await service._update_user_state(state, role, user_profile.get("id"))


@auth_router.message(RegistrationStates.waiting_for_code)
async def register_code_handler(message: Message, state: FSMContext) -> None:
    """Обрабатывает введенный код регистрации."""
    telegram_id = message.from_user.id
    code = (message.text or "").strip()
    loading_msg = await message.answer(AuthMessages.CHECKING_CODE)

    try:
        result = await client_manager.auth.auth_by_code(telegram_id, code)
        await loading_msg.delete()

        if result and result.get("success"):
            await service._handle_registration_success(message, state, result.get("user", {}))
        else:
            await service._handle_registration_failure(message, state, result or {})
    except Exception as e:
        await loading_msg.delete()
        logger.error(
            AuthServiceMessages.REGISTRATION_CRITICAL_ERROR.format(telegram_id, e),
            exc_info=True,
        )
        await state.clear()
        await message.answer(AuthServiceMessages.CRITICAL_REGISTRATION_ERROR)


@auth_router.message(Command("me"))
async def user_stats_handler(message: Message, user_data: dict):
    """Получить статистику пользователя (требует авторизации)."""
    if not user_data.get("role") or user_data.get("role") == UserRole.GUEST:
        await message.answer(ErrorMessages.Auth.FORBIDDEN)
        return

    await message.answer(AuthMessages.ME_LOADING)
    telegram_id = message.from_user.id
    # Просто вызываем сервисную функцию, которая делает всю работу
    stats_text = await service.get_user_stats_text(telegram_id)
    await message.answer(stats_text)


@auth_router.message(Command("logout"))
async def logout_handler(message: Message, state: FSMContext, user_data: dict):
    """Обработчик команды /logout."""
    if not user_data:
        await message.answer(AuthMessages.NOT_LOGGED_IN)
        return

    await state.clear()
    await message.answer(AuthMessages.LOGOUT_SUCCESS)
