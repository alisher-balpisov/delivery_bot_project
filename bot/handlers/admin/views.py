from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.admin_client import AdminClient
from bot.dto import UserDTO
from bot.filters.filters import RoleFilter
from bot.handlers.keyboards import get_back_to_menu_keyboard, get_role_selection_keyboard
from bot.messages import AdminMessages

from . import service

admin_router = Router(name="admin_handlers")
admin_router.message.filter(RoleFilter(UserRole.ADMIN))
admin_router.callback_query.filter(RoleFilter(UserRole.ADMIN))

logger = get_logger(__name__)


@admin_router.message(Command(UserRole.ADMIN.value))
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
    """Отображает системную статистику..."""
    try:
        logger.info(f"Обработка запроса системной статистики от пользователя {user.telegram_id}")

        is_callback = isinstance(event, CallbackQuery)

        if is_callback:
            if event.message is None:
                logger.warning(
                    f"Получена CallbackQuery без связанного сообщения для пользователя {user.telegram_id}. "
                    "Возможно, сообщение было удалено или callback относится к inline сообщению."
                )
                await event.answer()
                return
            await service._send_system_stats(
                event.message, user.telegram_id, admin_client, edit=True
            )
            await event.answer()
        else:
            await service._send_system_stats(event, user.telegram_id, admin_client, edit=False)

        logger.info(f"Успешно отправлена системная статистика пользователю {user.telegram_id}")

    except Exception as e:
        logger.error(
            f"Ошибка в system_stats_handler для пользователя {user.telegram_id}: {e}", exc_info=True
        )
        # Отправка сообщения об ошибке
        error_message = "Произошла ошибка при получении статистики. Попробуйте позже."
        try:
            if isinstance(event, CallbackQuery) and event.message:
                await event.message.answer(error_message)
            elif isinstance(event, Message):
                await event.answer(error_message)
        except Exception as inner_e:
            logger.error(
                f"Не удалось отправить сообщение об ошибке пользователю {user.telegram_id}: {inner_e}"
            )

        if isinstance(event, CallbackQuery):
            await event.answer()


@admin_router.message(Command("broadcast"))
async def broadcast_handler(message: Message):
    """Массовая рассылка (только для админов)."""
    await message.answer(AdminMessages.BROADCAST_IN_DEV)
