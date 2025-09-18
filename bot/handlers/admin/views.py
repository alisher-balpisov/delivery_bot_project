from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.admin_client import AdminClient
from bot.clients.system_client import SystemClient
from bot.dto import UserDTO
from bot.filters.filters import RoleFilter
from bot.handlers.keyboards import get_back_to_menu_keyboard, get_role_selection_keyboard
from bot.messages import AdminMessages, CommonMessages

from . import service

admin_router = Router(name="admin_handlers")
admin_router.message.filter(RoleFilter(UserRole.ADMIN))
admin_router.callback_query.filter(RoleFilter(UserRole.ADMIN))

logger = get_logger(__name__)


@admin_router.message(Command("admin"))
async def admin_handler(message: Message, user: UserDTO):
    """Отображает главное меню администратора."""
    text, keyboard = service.get_admin_menu()
    await message.answer(text, reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_back_to_menu")
async def admin_back_to_menu_handler(callback: CallbackQuery):
    """Обрабатывает кнопку 'Назад' для возврата в главное меню."""
    text, keyboard = service.get_admin_menu()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@admin_router.callback_query(F.data == "admin_create_code")
async def admin_create_code_menu_handler(callback: CallbackQuery):
    """Отображает меню выбора роли для создания кода."""
    keyboard = get_role_selection_keyboard()
    await callback.message.edit_text(AdminMessages.CREATE_CODE_PROMPT, reply_markup=keyboard)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_create_code_"))
async def admin_create_code_for_role_handler(
    callback: CallbackQuery, admin_client: AdminClient, user: UserDTO
):
    """Создает код для выбранной роли."""
    role_str = callback.data.split("_")[-1]

    try:
        role = UserRole(role_str)
        telegram_id = user.telegram_id

        response_text = await service.create_registration_code(
            telegram_id=telegram_id,
            admin_client=admin_client,
            role=role,
        )

        await callback.message.answer(response_text, parse_mode="Markdown")
        text, keyboard = service.get_admin_menu()
        await callback.message.edit_text(text, reply_markup=keyboard)

    except ValueError:
        await callback.message.answer(AdminMessages.INVALID_ROLE)

    await callback.answer()


@admin_router.callback_query(F.data == "admin_view_codes")
async def admin_view_codes_handler(
    callback: CallbackQuery, admin_client: AdminClient, user: UserDTO
):
    """Отображает список кодов регистрации."""
    await callback.message.edit_text(AdminMessages.LOADING_CODES)
    telegram_id = user.telegram_id

    response_text = await service.get_formatted_codes(telegram_id, admin_client)

    keyboard = get_back_to_menu_keyboard()
    await callback.message.edit_text(response_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@admin_router.message(Command("system_stats"))
@admin_router.callback_query(F.data == "system_stats")
async def system_stats_handler(
    event: Message | CallbackQuery, admin_client: AdminClient, user: UserDTO
) -> None:
    """
    Отображает системную статистику для администратора.

    Обрабатывает как команды сообщений, так и callback запросы.
    Для callback проверяет наличие связанного сообщения.
    """
    telegram_id = user.telegram_id
    logger.info(f"Обработка запроса системной статистики от пользователя {telegram_id}")

    try:
        if isinstance(event, CallbackQuery):
            await service._handle_callback_stats(event, telegram_id, admin_client)
        else:
            await service._handle_message_stats(event, telegram_id, admin_client)

        logger.info(f"Успешно отправлена системная статистика пользователю {telegram_id}")

    except Exception as e:
        await service._handle_stats_error(event, telegram_id, e)


@admin_router.message(Command("broadcast"))
async def broadcast_handler(message: Message):
    """Массовая рассылка (только для админов)."""
    await message.answer(AdminMessages.BROADCAST_IN_DEV)


@admin_router.message(Command("test_api"))
async def test_api_connection(message: Message, user: UserDTO, system_client: SystemClient):
    """Тестирование соединения с API (требует авторизации)."""
    await message.answer(CommonMessages.API_TESTING)
    response_text = await service.get_api_status_text(system_client)
    await message.answer(response_text)
