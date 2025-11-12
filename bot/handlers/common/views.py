from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.clients.auth_client import AuthClient
from bot.clients.disputes_client import DisputesClient
from bot.dto import UserDTO
from bot.filters.filters import IsAuthenticatedFilter
from bot.messages import DisputeMessages
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

from . import service

common_router = Router(name="common_handlers")
common_router.message.filter(IsAuthenticatedFilter())
common_router.callback_query.filter(IsAuthenticatedFilter())


@common_router.message(Command("orders"))
async def orders_handler(message: Message, user: UserDTO):
    """Показать заказы в зависимости от роли (требует авторизации)."""
    text = service.get_orders_text_by_role(user.role)
    await message.answer(text)


@common_router.message(Command("dispute"))
async def dispute_handler(message: Message, user: UserDTO):
    """Открыть новый спор (для магазинов и курьеров)."""
    text = service.get_new_dispute_text()
    await message.answer(text)


@common_router.message(Command("disputes"))
async def disputes_handler(
    message: Message,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    user_storage: UserDataStorage,
):
    """Показать споры пользователя."""
    # Создаем TokenManager
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(message.from_user.id)

    await message.answer(DisputeMessages.LOADING_DISPUTES)
    response_text = await service.get_user_disputes_text(token, disputes_client)
    await message.answer(response_text)
