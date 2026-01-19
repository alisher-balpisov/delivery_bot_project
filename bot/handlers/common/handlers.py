# handlers.py — /start, /help, общие хендлеры
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from bot.clients.admin_client import AdminClient
from bot.clients.auth_client import AuthClient
from bot.clients.shops_client import ShopsClient
from bot.clients.users_client import UsersClient
from bot.dto import UserDTO
from bot.handlers.admin import service as admin_service
from bot.handlers.auth.service import get_user_profile_by_token
from bot.handlers.courier.keyboards import get_courier_main_keyboard
from bot.handlers.shop.keyboards import get_shop_main_menu_keyboard
from bot.handlers.shop.messages import ShopMessages
from bot.messages import AuthMessages
from bot.redis_storage import UserDataStorage
from bot.states import RegistrationStates
from bot.utils.token_manager import TokenManager

logger = get_logger(__name__)

router = Router(name="common_handlers")


async def show_menu_by_role(
    event: Message | CallbackQuery,
    role: UserRole,
    name: str,
    admin_client=None,
    shops_client: ShopsClient | None = None,
    token: str | None = None,
):
    """Отображает меню в зависимости от роли пользователя."""
    if role == UserRole.ADMIN:
        await admin_service.show_admin_main_menu(event, name, admin_client, token)
    elif role == UserRole.SHOP:
        text = f"📋 Привет, SHOP {name}!"
        if shops_client and token:
            try:
                stats = await shops_client.get_shop_stats(token)
                text = ShopMessages.MAIN_MENU.format(
                    active_orders=stats.active_orders,
                    today_orders=stats.orders_today,
                    active_disputes=stats.active_disputes,
                )
            except Exception as e:
                logger.error(f"Ошибка при получении статистики магазина: {e}")

        keyboard = get_shop_main_menu_keyboard()
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


async def handle_authorized_user(
    message: Message,
    users_client: UsersClient,
    user_storage: UserDataStorage,
    telegram_id: int,
    access_token: str,
    admin_client: AdminClient | None = None,
    shops_client: ShopsClient | None = None,
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

    await show_menu_by_role(message, role, name, admin_client, shops_client, token=access_token)


@router.message(Command("start"))
async def start_handler(
    message: Message,
    state: FSMContext,
    user: UserDTO,
    auth_client: AuthClient,
    users_client: UsersClient,
    user_storage: UserDataStorage,
    admin_client: AdminClient,
    shops_client: ShopsClient,
):
    """Обработчик команды /start. Показывает главное меню или приветствие для новых пользователей."""
    telegram_id = message.from_user.id
    logger.info(f"/start от пользователя {telegram_id} (роль: {user.role.value})")

    # === 1. Проверяем, авторизован ли пользователь ===
    if user.role != UserRole.GUEST:
        # Пользователь зарегистрирован - показываем главное меню
        logger.info(f"Зарегистрированный пользователь {telegram_id}, показываем меню")

        token_manager = TokenManager(auth_client, user_storage)
        access_token = await token_manager.get_token(telegram_id)

        if access_token:
            return await handle_authorized_user(
                message,
                users_client,
                user_storage,
                telegram_id,
                access_token,
                admin_client,
                shops_client,
            )
        else:
            logger.warning(f"Не удалось получить токен для пользователя {telegram_id}")
            await message.answer(
                "⚠️ Произошла ошибка при загрузке данных. Попробуйте команду /logout, а затем /register"
            )
            return

    # === 2. Пользователь - GUEST, проверяем незавершенную регистрацию ===
    # Делаем явный запрос login для проверки статуса регистрации
    login_result = await auth_client.login(telegram_id)

    if login_result.status_code == 403:
        # Пользователь существует, но не завершил регистрацию
        logger.info(f"Пользователь {telegram_id} не завершил регистрацию")
        await state.set_state(RegistrationStates.waiting_for_code)
        return await message.answer(
            "⚠️ Вы начали регистрацию, но не завершили её.\n\n" + AuthMessages.ENTER_CODE
        )

    # === 3. Совершенно новый пользователь ===
    logger.info(f"Новый пользователь {telegram_id}, регистрируем как гостя")

    # Регистрируем пользователя в БД как гостя
    reg_result = await auth_client.register_guest(telegram_id, message.from_user.username)

    if reg_result.success:
        logger.info(f"Пользователь {telegram_id} успешно добавлен в БД как Guest")
        await user_storage.delete_user_data(telegram_id)
    else:
        logger.error(f"Ошибка регистрации гостя {telegram_id}: {reg_result.detail}")

    await state.set_state(RegistrationStates.waiting_for_code)
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Для начала работы вам необходимо получить код приглашения у администратора.\n\n"
        + AuthMessages.ENTER_CODE
    )


@router.callback_query(F.data == "show_main_menu")
async def show_main_menu_handler(
    callback: CallbackQuery,
    user: UserDTO,
    auth_client: AuthClient,
    admin_client: AdminClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Возврат в главное меню."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    await show_menu_by_role(
        event=callback,
        role=user.role,
        name=user.name,
        admin_client=admin_client,
        shops_client=shops_client,
        token=token,
    )
    await callback.answer()
