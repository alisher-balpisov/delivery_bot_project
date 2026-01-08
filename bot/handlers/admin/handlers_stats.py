# handlers_stats.py — Хендлеры статистики
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from bot.clients.admin_client import AdminClient
from bot.clients.auth_client import AuthClient
from bot.dto import UserDTO
from bot.filters.filters import RoleFilter
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

from . import service

logger = get_logger(__name__)

router = Router(name="admin_stats_handlers")
router.message.filter(RoleFilter(UserRole.ADMIN))
router.callback_query.filter(RoleFilter(UserRole.ADMIN))


@router.callback_query(F.data == "show_statistics")
async def show_statistics_handler(
    callback: CallbackQuery,
    user: UserDTO,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
) -> None:
    """Отображает детальную системную статистику при нажатии на кнопку."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(user.telegram_id)

    logger.info(f"Обработка запроса статистики от пользователя {user.telegram_id}")
    try:
        await service._handle_callback_stats(callback, token, admin_client)
        logger.info(f"Успешно отправлена статистика пользователю {user.telegram_id}")
    except Exception as e:
        await service._handle_stats_error(callback, user.telegram_id, e)


@router.message(Command("system_stats"))
@router.callback_query(F.data == "system_stats")
async def system_stats_handler(
    event: Message | CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
    user: UserDTO,
) -> None:
    """Отображает системную статистику для администратора."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(user.telegram_id)

    logger.info(f"Обработка запроса системной статистики от пользователя {user.telegram_id}")
    try:
        if isinstance(event, CallbackQuery):
            await service._handle_callback_stats(event, token, admin_client)
        else:
            await service._handle_message_stats(event, token, admin_client)
        logger.info(f"Успешно отправлена системная статистика пользователю {user.telegram_id}")
    except Exception as e:
        await service._handle_stats_error(event, user.telegram_id, e)
