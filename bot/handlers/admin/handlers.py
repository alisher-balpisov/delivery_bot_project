# handlers.py — Главное меню админа (/admin, навигация)
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from bot.clients.admin_client import AdminClient
from bot.clients.auth_client import AuthClient
from bot.clients.system_client import SystemClient
from bot.dto import UserDTO
from bot.filters.filters import RoleFilter
from bot.messages import AdminMessages, CommonMessages
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

from . import service

logger = get_logger(__name__)

router = Router(name="admin_main_handlers")
router.message.filter(RoleFilter(UserRole.ADMIN))
router.callback_query.filter(RoleFilter(UserRole.ADMIN))


@router.message(Command("admin"))
async def admin_handler(
    message: Message,
    user: UserDTO,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Отображает главное меню администратора."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(message.from_user.id)
    await service.show_admin_main_menu(message, user.name, admin_client, token)


@router.callback_query(F.data == "admin_back_to_menu")
async def back_to_menu_handler(
    callback: CallbackQuery,
    user: UserDTO,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Возврат в главное меню админа."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)
    await service.show_admin_main_menu(callback, user.name, admin_client, token)


@router.message(Command("broadcast"))
async def broadcast_handler(message: Message):
    """Массовая рассылка (только для админов)."""
    await message.answer(AdminMessages.BROADCAST_IN_DEV)


@router.message(Command("test_api"))
async def test_api_connection(message: Message, system_client: SystemClient):
    """Тестирование соединения с API (не требует авторизации)."""
    await message.answer(CommonMessages.API_TESTING)
    response_text = await service.get_api_status_text(system_client)
    await message.answer(response_text)
