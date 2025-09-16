from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from bot.filters import RoleFilter
from bot.handlers.keyboards import get_back_to_menu_keyboard, get_role_selection_keyboard
from bot.messages import AdminMessages

from . import service

admin_router = Router(name="admin_handlers")


@admin_router.message(Command(UserRole.ADMIN.value), RoleFilter(UserRole.ADMIN))
async def admin_handler(message: Message, user_data: dict):
    """Отображает главное меню администратора."""
    text, keyboard = service.get_admin_menu()
    await message.answer(text, reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_back_to_menu", RoleFilter(UserRole.ADMIN))
async def admin_back_to_menu_handler(callback: CallbackQuery):
    """Обрабатывает кнопку 'Назад' для возврата в главное меню."""
    text, keyboard = service.get_admin_menu()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@admin_router.callback_query(F.data == "admin_create_code", RoleFilter(UserRole.ADMIN))
async def admin_create_code_menu_handler(callback: CallbackQuery):
    """Отображает меню выбора роли для создания кода."""
    keyboard = get_role_selection_keyboard()
    await callback.message.edit_text(AdminMessages.CREATE_CODE_PROMPT, reply_markup=keyboard)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_create_code_"), RoleFilter(UserRole.ADMIN))
async def admin_create_code_for_role_handler(callback: CallbackQuery):
    """Создает код для выбранной роли."""
    # Не отправляем "Создаю код...", чтобы избежать лишних дерганий интерфейса
    role_str = callback.data.split("_")[-1]

    try:
        role = UserRole(role_str)
        telegram_id = callback.from_user.id

        # Вся логика создания и форматирования ответа - в сервисе
        response_text = await service.create_registration_code(telegram_id, role)

        # Возвращаемся в главное меню после ответа
        await callback.message.answer(response_text, parse_mode="Markdown")
        text, keyboard = service.get_admin_menu()
        await callback.message.edit_text(text, reply_markup=keyboard)

    except ValueError:
        await callback.message.answer(AdminMessages.INVALID_ROLE)

    await callback.answer()


@admin_router.callback_query(F.data == "admin_view_codes", RoleFilter(UserRole.ADMIN))
async def admin_view_codes_handler(callback: CallbackQuery):
    """Отображает список кодов регистрации."""
    await callback.message.edit_text(AdminMessages.LOADING_CODES)
    telegram_id = callback.from_user.id

    # Сервис делает всю работу и возвращает готовый текст
    text = await service.get_formatted_codes(telegram_id)

    keyboard = get_back_to_menu_keyboard()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@admin_router.message(Command("system_stats"), RoleFilter(UserRole.ADMIN))
@admin_router.callback_query(F.data == "system_stats", RoleFilter(UserRole.ADMIN))
async def system_stats_handler(event: Message | CallbackQuery):
    """Отображает системную статистику."""
    target_message = event.message if isinstance(event, CallbackQuery) else event
    await target_message.answer(AdminMessages.SYSTEM_STATS_LOADING)

    user_id = event.from_user.id
    # Сервис делает всю работу и возвращает готовый текст
    stats_text = await service.get_system_stats_text(user_id)

    await target_message.answer(stats_text)
    if isinstance(event, CallbackQuery):
        await event.answer()


# Обработчик для массовой рассылки оставлен как заглушка
@admin_router.message(Command("broadcast"), RoleFilter(UserRole.ADMIN))
async def broadcast_handler(message: Message):
    """Массовая рассылка (только для админов)."""
    await message.answer(AdminMessages.BROADCAST_IN_DEV)
