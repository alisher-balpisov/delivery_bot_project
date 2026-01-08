from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.core.logging import get_logger
from bot.clients.admin_client import AdminClient
from bot.clients.auth_client import AuthClient
from bot.clients.disputes_client import DisputesClient
from bot.clients.users_client import UsersClient
from bot.constants import UserRole
from bot.dto import UserDTO
from bot.filters.filters import IsAuthenticatedFilter
from bot.handlers.admin import service as admin_service
from bot.handlers.auth.service import get_user_profile_by_token
from bot.handlers.courier.keyboards import get_courier_main_keyboard
from bot.handlers.shop.keyboards import get_shop_main_keyboard
from bot.messages import AuthMessages, DisputeMessages
from bot.redis_storage import UserDataStorage
from bot.states import RegistrationStates
from bot.utils.token_manager import TokenManager

from . import service

logger = get_logger(__name__)

common_router = Router(name="common_handlers")
common_router.message.filter(IsAuthenticatedFilter())
common_router.callback_query.filter(IsAuthenticatedFilter())


@common_router.message(Command("start"))
async def start_handler(
    message: Message,
    state: FSMContext,
    user: UserDTO,
    auth_client: AuthClient,
    users_client: UsersClient,
    user_storage: UserDataStorage,
    admin_client: AdminClient,
):
    telegram_id = message.from_user.id
    logger.info(f"/start от пользователя {telegram_id}")

    token_manager = TokenManager(auth_client, user_storage)

    # === 1. Получаем валидный токен (проверяет Redis, делает login/refresh при необходимости) ===
    access_token = await token_manager.get_token(telegram_id)

    if access_token:
        logger.info("Токен получен (из кэша или через login)")
        return await handle_authorized_user(
            message, users_client, user_storage, telegram_id, access_token, admin_client
        )

    # === 2. Токен не получен - проверяем, не незавершенная ли регистрация ===
    # TokenManager.get_token() уже попытался сделать login через API
    # Если вернулся None, нужно проверить статус через явный вызов
    login_result = await auth_client.login(telegram_id)

    if login_result.status_code == 403:
        # Пользователь существует, но не завершил регистрацию
        logger.info(f"Пользователь {telegram_id} не завершил регистрацию")
        await state.set_state(RegistrationStates.waiting_for_code)
        return await message.answer(
            "⚠️ Вы начали регистрацию, но не завершили её.\n\n" + AuthMessages.ENTER_CODE
        )

    # === 3. Совершенно новый пользователь ===
    logger.info(f"Новый пользователь {telegram_id}")
    await state.clear()
    await message.answer(AuthMessages.WELCOME_NEW_USER)


async def show_menu_by_role(
    event: Message | CallbackQuery,
    role: UserRole,
    name: str,
    admin_client=None,
    token: str | None = None,
):
    if role == UserRole.ADMIN:
        await admin_service.show_admin_main_menu(event, name, admin_client, token)
    elif role == UserRole.SHOP:
        text = f"📋 Привет, SHOP {name}!"
        keyboard = get_shop_main_keyboard()
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=keyboard)
        else:
            await event.answer(text, reply_markup=keyboard)
    elif role == UserRole.COURIER:
        text = f"👋 Привет, курьер {name}!"
        keyboard = get_courier_main_keyboard()
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=keyboard)
        else:
            await event.answer(text, reply_markup=keyboard)


@common_router.callback_query(F.data == "show_main_menu")
async def show_main_menu_handler(
    callback: CallbackQuery,
    user: UserDTO,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Возврат в главное меню."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    await show_menu_by_role(
        event=callback, role=user.role, name=user.name, admin_client=admin_client, token=token
    )
    await callback.answer()


async def handle_authorized_user(
    message: Message,
    users_client: UsersClient,
    user_storage: UserDataStorage,
    telegram_id: int,
    access_token: str,
    admin_client: AdminClient | None = None,
):
    """Общая логика для случаев, когда токен валиден."""

    profile = await get_user_profile_by_token(access_token, users_client)

    if not profile:
        return await message.answer("Ошибка загрузки профиля. Попробуйте позже.")

    # --- Унифицируем тип данных ---
    if isinstance(profile, UserDTO):
        profile = profile.model_dump()

    # Теперь profile гарантированно dict
    await user_storage.update_user_data(
        telegram_id,
        {
            "user_id": profile.get("id"),
            "name": profile.get("name"),
            "role": profile.get("role"),
            "username": profile.get("username"),
        },
    )

    # role должен быть Enum
    role = UserRole(profile.get("role"))
    name = profile.get("name") or "пользователь"

    # Для администратора при наличии admin_client передаем его для получения статистики
    if role == UserRole.ADMIN:
        # admin_client передается через DI в start_handler, если None - показывается простое приветствие
        await show_menu_by_role(message, role, name, admin_client, access_token)
    else:
        await show_menu_by_role(message, role, name)


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
