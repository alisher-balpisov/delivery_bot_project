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
from bot.handlers.admin.keyboards import get_registration_code_menu_keyboard
from bot.handlers.admin.messages import AdminMessages as AM
from bot.handlers.keyboards import get_role_selection_keyboard
from bot.messages import AdminMessages, CommonMessages
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

from . import service

admin_router = Router(name="admin_handlers")
admin_router.message.filter(RoleFilter(UserRole.ADMIN))
admin_router.callback_query.filter(RoleFilter(UserRole.ADMIN))

logger = get_logger(__name__)

# Константа для количества кодов на странице
CODES_PER_PAGE = 5


@admin_router.callback_query(F.data == "get_registration_code_menu")
async def get_registration_code_menu_handler(callback: CallbackQuery):
    """Открывает меню 'Код регистрации'"""
    await callback.message.edit_text(
        AM.REGISTRATION_CODE_MENU, reply_markup=get_registration_code_menu_keyboard()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_back_to_registration_menu")
async def admin_back_to_registration_menu_handler(callback: CallbackQuery):
    """Возврат в меню 'Код регистрации'."""
    await callback.message.edit_text(
        AM.REGISTRATION_CODE_MENU, reply_markup=get_registration_code_menu_keyboard()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery, user: UserDTO):
    """Возврат в главное меню админа."""
    await service.show_admin_main_menu(callback, user.name)


@admin_router.message(Command("admin"))
async def admin_handler(message: Message, user: UserDTO):
    """Отображает главное меню администратора."""
    text, keyboard = service.get_admin_menu()
    await message.answer(text, reply_markup=keyboard)


# @admin_router.callback_query(F.data == "admin_back_to_menu")
# async def admin_back_to_menu_handler(callback: CallbackQuery):
#     """Обрабатывает кнопку 'Назад' для возврата в главное меню."""
#     text, keyboard = service.get_admin_menu()
#     await callback.message.edit_text(text, reply_markup=keyboard)
#     await callback.answer()


@admin_router.callback_query(F.data == "admin_create_code")
async def admin_create_code_menu_handler(callback: CallbackQuery):
    """Отображает меню выбора роли для создания кода."""
    keyboard = get_role_selection_keyboard()
    await callback.message.edit_text(AdminMessages.CREATE_CODE_PROMPT, reply_markup=keyboard)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_create_code_"))
async def admin_create_code_for_role_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Создает код для выбранной роли."""
    # Создаем TokenManager
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    role_str = callback.data.split("_")[-1]

    try:
        role = UserRole(role_str)
        response_text = await service.create_registration_code(
            token=token,
            admin_client=admin_client,
            role=role,
        )

        # Импортируем клавиатуру для возврата
        from bot.handlers.admin.keyboards import get_back_to_registration_menu_keyboard

        # Редактируем текущее сообщение с результатом и кнопкой возврата
        await callback.message.edit_text(
            response_text,
            parse_mode="Markdown",
            reply_markup=get_back_to_registration_menu_keyboard(),
        )

    except ValueError:
        await callback.message.edit_text(AdminMessages.INVALID_ROLE)
    await callback.answer()


@admin_router.callback_query(F.data == "admin_view_codes")
@admin_router.callback_query(F.data.startswith("admin_codes_page_"))
@admin_router.callback_query(F.data.startswith("admin_codes_filter_"))
async def admin_view_codes_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Отображает список кодов регистрации с пагинацией и фильтрацией."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    # Парсинг параметров из callback_data
    page = 1
    filter_status = "all"

    # Пытаемся получить текущее состояние фильтра из текста кнопки (если это пагинация)
    # В реальном приложении лучше использовать FSM или Redis для хранения состояния фильтра
    # Здесь для простоты будем сбрасывать фильтр при переходе в меню, но сохранять при пагинации если получится
    # Пока реализуем базовую логику: при клике на фильтр - обновляем список, при клике на страницу - обновляем страницу

    if callback.data.startswith("admin_codes_page_"):
        # Формат: admin_codes_page_{page}_{filter_status}
        parts = callback.data.split("_")
        page = int(parts[3])
        if len(parts) > 4:
            filter_status = parts[4]
    elif callback.data.startswith("admin_codes_filter_"):
        filter_status = callback.data.split("_")[-1]
        page = 1

    # Определяем параметры для API
    is_used = None
    if filter_status == "active":
        is_used = False
    elif filter_status == "used":
        is_used = True

    result = await admin_client.get_registration_codes(
        token=token, page=page, limit=CODES_PER_PAGE, is_used=is_used
    )

    # Если токен истек (401), пробуем обновить и повторить запрос
    if result.status_code == 401:
        logger.warning(
            f"Получен 401 при запросе кодов. Пробуем обновить токен для {callback.from_user.id}"
        )
        token = await token_manager.get_token(callback.from_user.id, force_refresh=True)
        if token:
            result = await admin_client.get_registration_codes(
                token=token, page=page, limit=CODES_PER_PAGE, is_used=is_used
            )

    if not result.success:
        await callback.answer("Ошибка при получении кодов", show_alert=True)
        return

    data = result.data
    codes = data.get("items", [])
    total_count = data.get("total", 0)
    # Исправление: если total_count = 0, total_pages должен быть 1, а не 0
    total_pages = max(1, (total_count + CODES_PER_PAGE - 1) // CODES_PER_PAGE)

    from bot.handlers.admin.keyboards import get_registration_codes_list_keyboard

    keyboard = get_registration_codes_list_keyboard(
        codes=codes, page=page, total_pages=total_pages, filter_status=filter_status
    )

    text = f"📋 **Список кодов регистрации**\nВсего: {total_count}"

    # Если это обновление (пагинация/фильтр), редактируем, иначе отправляем
    if callback.message.text:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_code_select_"))
async def admin_code_details_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Отображает детали выбранного кода."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    code_id = int(callback.data.split("_")[-1])
    result = await admin_client.get_registration_code_details(token, code_id)

    if result.status_code == 401:
        token = await token_manager.get_token(callback.from_user.id, force_refresh=True)
        if token:
            result = await admin_client.get_registration_code_details(token, code_id)

    # Исправление: добавлена проверка наличия данных
    if not result.success or not result.data:
        await callback.answer("Ошибка при получении деталей кода", show_alert=True)
        return

    code = result.data
    is_active = not code.get("is_used") and not code.get(
        "is_expired"
    )  # is_expired нет в модели, но логика может быть на бэке
    # В модели есть expires_at, проверим его на клиенте или просто доверимся is_used
    # Для простоты UI считаем активным если !is_used. Деактивация делает его used/expired.

    status_text = "🔴 Использован/Просрочен" if code.get("is_used") else "🟢 Активен"
    role_name = "Курьер" if code.get("role") == "courier" else "Магазин"

    text = (
        f"🎫 **Код:** `{code.get('code')}`\n"
        f"👤 **Роль:** {role_name}\n"
        f"📊 **Статус:** {status_text}\n"
        f"📅 **Создан:** {code.get('created_at')}\n"
        f"⏳ **Истекает:** {code.get('expires_at')}\n"
    )

    from bot.handlers.admin.keyboards import get_registration_code_details_keyboard

    keyboard = get_registration_code_details_keyboard(code_id, is_active)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_code_deactivate_"))
async def admin_code_deactivate_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Деактивирует код."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    code_id = int(callback.data.split("_")[-1])
    result = await admin_client.deactivate_registration_code(token, code_id)

    if result.status_code == 401:
        token = await token_manager.get_token(callback.from_user.id, force_refresh=True)
        if token:
            result = await admin_client.deactivate_registration_code(token, code_id)

    if result.success:
        await callback.answer("Код успешно деактивирован", show_alert=True)
        # Обновляем детали кода
        await admin_code_details_handler(callback, auth_client, admin_client, user_storage)
    else:
        await callback.answer(f"Ошибка: {result.detail}", show_alert=True)


@admin_router.message(Command("system_stats"))
@admin_router.callback_query(F.data == "system_stats")
async def system_stats_handler(
    event: Message | CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
    user: UserDTO,
) -> None:
    """Отображает системную статистику для администратора."""
    # Создаем TokenManager
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


@admin_router.message(Command("broadcast"))
async def broadcast_handler(message: Message):
    """Массовая рассылка (только для админов)."""
    await message.answer(AdminMessages.BROADCAST_IN_DEV)


@admin_router.message(Command("test_api"))
async def test_api_connection(message: Message, system_client: SystemClient):
    """Тестирование соединения с API (не требует авторизации)."""
    await message.answer(CommonMessages.API_TESTING)
    response_text = await service.get_api_status_text(system_client)
    await message.answer(response_text)
