# handlers.py — Меню курьера, смена смены
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from bot.clients.auth_client import AuthClient
from bot.filters.filters import RoleFilter
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

from .keyboards import get_courier_main_keyboard

logger = get_logger(__name__)

router = Router(name="courier_main_handlers")
router.message.filter(RoleFilter(UserRole.COURIER))
router.callback_query.filter(RoleFilter(UserRole.COURIER))


@router.message(Command("courier"))
@router.message(Command("menu"))
async def courier_menu_handler(
    message: Message,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Показывает главное меню курьера."""
    token_manager = TokenManager(auth_client, user_storage)
    await token_manager.get_token(message.from_user.id)

    keyboard = get_courier_main_keyboard()
    await message.answer("📲 Главное меню курьера:", reply_markup=keyboard)


# TODO: Добавить хендлеры для start_shift, end_shift когда будет реализован backend
