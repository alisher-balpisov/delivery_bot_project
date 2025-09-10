"""
Обработчики команд и сообщений для Telegram бота
"""

from functools import cache

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.core.logging import get_logger

from bot.client_manager import client_manager
from bot.constants import ROLE_COMMANDS, DisputeStatus, UserRole

logger = get_logger(__name__)

# Публичный роутер (команды типа /help, /start)
public_router = Router(name="public_handlers")
# Защищенный роутер (требует авторизации)
protected_router = Router(name="protected_handlers")

DEFAULT_MENU_HEADER = "🏠 Главное меню:\n\n"
GUEST_ROLE = UserRole.GUEST


@protected_router.message(Command("test_api"))
async def test_api_connection(message: Message, user_data: dict):
    """Тестирование соединения с API (требует авторизации)."""
    await message.answer("🔄 Тестирую соединение с API...")
    try:
        data = await client_manager.system.health_check()
        if data and data.get("status") == "ok":
            text = (
                "✅ API соединение успешно!\n\n"
                f"🏥 Статус: {data.get('status', 'N/A')}\n"
                f"📱 Приложение: {data.get('app', 'N/A')}\n"
                f"🏷️ Версия: {data.get('version', 'N/A')}\n"
                f"🕐 Время: {data.get('timestamp', 'N/A')}"
            )
        else:
            text = f"❌ Ошибка API: {data.get('detail', 'не удалось получить статус')}"
    except httpx.RequestError as e:
        text = f"❌ Ошибка подключения к API: {e}"
    except Exception as e:
        logger.error(f"Неожиданная ошибка в test_api_connection: {e}", exc_info=True)
        text = "❌ Произошла непредвиденная ошибка."

    await message.answer(text)


@protected_router.message(Command("user_stats"))
async def user_stats_handler(message: Message, user_data: dict):
    """Получить статистику пользователя из API (требует авторизации)."""
    token = user_data.get("access_token")
    await message.answer("📊 Получаю вашу статистику...")

    try:
        user_info = await client_manager.users.get_user_profile(token)
        if user_info and user_info.get("success") is not False:
            text = (
                "📈 Ваша статистика:\n\n"
                f"🆔 ID: {user_info.get('id', 'N/A')}\n"
                f"👤 Имя: {user_info.get('name', 'не указано')}\n"
                f"👑 Роль: {user_info.get('role', 'неизвестна').upper()}\n"
                f"📱 Telegram ID: {user_info.get('telegram_id', 'N/A')}\n"
                f"✨ Статус: {'активен' if user_info.get('is_active', True) else 'деактивирован'}\n"
                f"🚫 Блокировка: {'да' if user_info.get('is_blocked', False) else 'нет'}"
            )
        else:
            text = (
                f"❌ Ошибка получения статистики: {user_info.get('detail', 'Неизвестная ошибка')}"
            )
    except httpx.RequestError as e:
        text = f"❌ Ошибка подключения к API: {e}"
    except Exception as e:
        logger.error(f"Неожиданная ошибка в user_stats_handler: {e}", exc_info=True)
        text = "❌ Произошла непредвиденная ошибка."

    await message.answer(text)


@cache
def generate_menu_text(role: str) -> str:
    """Генерирует текст главного меню на основе роли пользователя.

    Args:
        role (str): Роль пользователя ('admin', 'shop', 'courier' или 'guest').

    Returns:
        str: Форматированный текст меню.
    """
    if not role:
        role = GUEST_ROLE

    text = DEFAULT_MENU_HEADER
    text += "👋 Добро пожаловать!\n\n"

    # Общие команды
    text += "📋 Основные команды:\n"
    text += "/help - Справка\n"

    if role != GUEST_ROLE:
        text += "/me - Мой профиль\n"
        text += "/logout - Выход\n"
        text += "/user_stats - Статистика\n"

    # Ролевые команды из конфига
    role_config = ROLE_COMMANDS.get(role)
    if role_config:
        text += f"\n{role_config['icon']} {role_config['title']}\n"
        text += "".join(role_config["commands"])

    if role == UserRole.ADMIN:
        text += "/admin - Панель администратора\n"

    return text


@protected_router.callback_query(F.data == "show_menu")
async def show_menu_callback(callback: CallbackQuery, user_data: dict):
    """Показать меню команд (через callback, требует авторизации).

    Args:
        callback (CallbackQuery): Объект callback от Telegram.
        user_data (dict): Данные пользователя из middleware.

    Raises:
        Aiogram exceptions при проблемах с Telegram API.
    """
    # Валидация входных данных
    if not user_data:
        logger.warning("user_data отсутствует в show_menu_callback")
        await callback.answer("❌ Ошибка: данные пользователя недоступны.")
        return

    if not callback.message:
        logger.error("callback.message отсутствует")
        await callback.answer("❌ Ошибка: сообщение недоступно.")
        return

    # Получение роли с fallback
    role = user_data.get("role", GUEST_ROLE)

    try:
        # Генерация текста меню
        text = generate_menu_text(role)

        # Обновление сообщения
        await callback.message.edit_text(text)

        # Подтверждение callback
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в show_menu_callback для роли {role}: {e}", exc_info=True)
        # Fallback: показать общее меню без ошибок
        try:
            await callback.message.edit_text(
                f"{DEFAULT_MENU_HEADER}❌ Произошла ошибка. Попробуйте /help"
            )
            await callback.answer("❌ Ошибка при загрузке меню")
        except Exception as fallback_e:
            logger.error(f"Ошибка fallback в show_menu_callback: {fallback_e}", exc_info=True)
            await callback.answer("❌ Критическая ошибка")


def generate_help_text(role: str) -> str:
    """Генерация текста справки по командам в зависимости от роли."""
    help_text = "🤖 Справка по командам:\n\n"
    help_text += "📋 Основные:\n"
    help_text += "/start - Авторизация\n"
    help_text += "/register - Регистрация\n"
    help_text += "/help - Эта справка\n"

    if role != UserRole.GUEST:
        help_text += "/me - Мой профиль\n"
        help_text += "/logout - Выход\n"

    role_config = ROLE_COMMANDS.get(role)
    if role_config:
        help_text += f"\n{role_config['icon']} {role_config['title']}\n"
        help_text += "".join(role_config["commands"])
    return help_text


@public_router.message(Command("help"))
async def help_handler(message: Message, user_data: dict):
    """Показать доступные команды."""
    role = user_data.get("role", UserRole.GUEST)
    await message.answer(generate_help_text(role))


@protected_router.message(Command("orders"))
async def orders_handler(message: Message, user_data: dict):
    """Показать заказы в зависимости от роли (требует авторизации)."""
    role = user_data.get("role", "unknown")
    if role == UserRole.SHOP:
        await message.answer("🏪 Ваши заказы:\n\n📦 Создайте новый заказ командой /new_order")
    elif role == UserRole.COURIER:
        await message.answer("🏍️ Назначенные заказы:\n\n🚚 Доступные заказы появятся здесь")
    elif role == UserRole.ADMIN:
        await message.answer(
            "👑 Управление заказами:\n\n⚙️ Все заказы системы доступны в панели администратора"
        )
    else:
        await message.answer("❓ Доступные заказы не найдены для вашей роли.")


@protected_router.message(Command("dispute"))
async def dispute_handler(message: Message, user_data: dict):
    """Открыть новый спор (для магазинов и курьеров)."""
    role = user_data.get("role", "unknown")
    if role not in [UserRole.SHOP, UserRole.COURIER]:
        await message.answer("❌ Доступ запрещен. Только магазины и курьеры могут открывать споры.")
        return

    await message.answer(
        "⚠️ Открыть спор:\n\n"
        "Если с доставкой возникли проблемы, отправьте ID заказа для открытия спора.\n"
        "Пример: /dispute 123\n\n"
        f"Статус: {DisputeStatus.OPEN.value} (будет установлен автоматически)"
    )


@protected_router.message(Command("disputes"))
async def disputes_handler(message: Message, user_data: dict):
    """Показать споры пользователя."""
    role = user_data.get("role", "unknown")
    if role not in [UserRole.SHOP, UserRole.COURIER, UserRole.ADMIN]:
        await message.answer("❌ Доступ запрещен.")
        return

    token = user_data.get("access_token")
    await message.answer("⚠️ Загружаю ваши споры...")

    try:
        disputes = await client_manager.disputes.get_my_disputes(token)
        if disputes and isinstance(disputes, list) and len(disputes) > 0:
            text = "⚠️ Ваши споры:\n\n"
            for dispute in disputes[:5]:
                status_emoji = {
                    DisputeStatus.OPEN: "🟡",
                    DisputeStatus.IN_REVIEW: "🟠",
                    DisputeStatus.RESOLVED: "🟢",
                    DisputeStatus.CLOSED: "🔴",
                }.get(DisputeStatus(dispute.get("status")), "⚪")

                text += (
                    "04d"
                    f"{status_emoji} {DisputeStatus(dispute.get('status')).value}\n"
                    f"📝 {dispute.get('description', 'без описания')[:100]}...\n\n"
                )
            await message.answer(text)
        else:
            await message.answer("⚠️ У вас нет активных споров.")
    except Exception as e:
        logger.error(f"Ошибка при получении споров: {e}", exc_info=True)
        await message.answer("❌ Ошибка при загрузке споров.")


@protected_router.message(Command(UserRole.ADMIN))
async def admin_handler(message: Message, user_data: dict):
    """Показать панель администратора (требует авторизации и роли admin)."""
    role = user_data.get("role", UserRole.GUEST)
    if role != UserRole.ADMIN:
        await message.answer(
            "❌ Доступ запрещен. Только администраторы могут использовать эту команду."
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Создать код", callback_data="admin_create_code"),
                InlineKeyboardButton(text="📋 Просмотр кодов", callback_data="admin_view_codes"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_system_stats"),
            ],
        ]
    )
    await message.answer("👑 Панель администратора:\n\nВыберите действие:", reply_markup=keyboard)


@protected_router.callback_query(F.data.startswith("admin_"))
async def admin_callback_handler(callback: CallbackQuery, user_data: dict):
    """Обработчик callback для админских функций."""
    data = callback.data
    token = user_data.get("access_token")

    try:
        if data == "admin_create_code":
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🏪 Магазин", callback_data="admin_create_code_shop"
                        ),
                        InlineKeyboardButton(
                            text="🏍️ Курьер", callback_data="admin_create_code_courier"
                        ),
                    ],
                    [
                        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_to_menu"),
                    ],
                ]
            )
            await callback.message.edit_text(
                "📝 Выберите роль для создания регистрационного кода:", reply_markup=keyboard
            )
            await callback.answer()
        elif data.startswith("admin_create_code_") and data != "admin_create_code":
            role = data.split("_")[-1]
            if role not in [UserRole.SHOP, UserRole.COURIER]:
                await callback.message.answer("❌ Неверная роль.")
                await callback.answer()
                return
            result = await client_manager.admin.create_registration_code(token, role)
            if result and result.get("success") is not False:
                code = result.get("code", "не указано")
                await callback.message.answer(
                    f"✅ Код для роли {role.upper()} создан: `{code}`", parse_mode="Markdown"
                )
                await admin_back_to_menu(callback)
            else:
                detail = result.get("detail", "неизвестная ошибка") if result else "ошибка связи"
                await callback.message.answer(f"❌ Ошибка создания кода: {detail}")
                await callback.answer()
        elif data == "admin_view_codes":
            await callback.message.edit_text("📋 Загружаю список кодов...")
            codes = await client_manager.admin.get_all_registration_codes(token)
            if codes and isinstance(codes, list):
                text = "📋 Регистрационные коды:\n\n"
                for code_info in codes[:10]:
                    text += f"Код: `{code_info.get('code', '?')}` Роль: {code_info.get('role', '?')} Статус: {'использован' if code_info.get('is_used') else 'активен'}\n"
                if len(codes) > 10:
                    text += f"\n... и ещё {len(codes) - 10} кодов"
                await callback.message.edit_text(text, parse_mode="Markdown")
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_to_menu")]
                    ]
                )
                await callback.message.edit_reply_markup(reply_markup=keyboard)
            else:
                await callback.message.edit_text("❌ Не удалось получить коды.")
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_to_menu")]
                    ]
                )
                await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer()
        elif data == "admin_system_stats":
            await callback.message.edit_text("📊 Загружаю статистику...")
            stats = await client_manager.admin.get_system_stats(token)
            if stats and isinstance(stats, dict):
                text = "📊 Системная статистика:\n\n"
                stats_data = [
                    f"Пользователей: {stats.get('total_users', 0)}",
                    f"Админов: {stats.get('total_admins', 0)}",
                    f"Магазинов: {stats.get('total_shops', 0)}",
                    f"Курьеров: {stats.get('total_couriers', 0)}",
                    f"Заказов: {stats.get('total_orders', 0)}",
                ]
                text += "\n".join(stats_data)
            else:
                text = "❌ Не удалось получить статистику."
            await callback.message.edit_text(text)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_to_menu")]
                ]
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer()
        elif data == "admin_back_to_menu":
            await admin_back_to_menu(callback)
    except Exception as e:
        logger.error(f"Ошибка в admin_callback_handler: {e}", exc_info=True)
        await callback.message.edit_text("❌ Произошла ошибка. Попробуйте позже.")
        await callback.answer()


@public_router.message(F.text)
async def handle_plain_text(message: Message, user_data: dict):
    """Обработчик обычных текстовых сообщений."""
    role = user_data.get("role", UserRole.GUEST)
    text_lower = message.text.lower()

    if text_lower in ["меню", "menu", "помощь"]:
        await message.answer("Используйте /help для просмотра команд")
    elif text_lower in ["статус", "status"]:
        status = "авторизован" if user_data.get("access_token") else "не авторизован"
        text = f"📊 Ваш статус: {status}\n👑 Роль: {role.upper()}\n"
        await message.answer(text)
    else:
        await message.answer(
            "👋 Неизвестная команда. Используйте /help для просмотра списка команд."
        )


async def admin_back_to_menu(callback: CallbackQuery):
    """Вернуться в главное меню админа."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Создать код", callback_data="admin_create_code"),
                InlineKeyboardButton(text="📋 Просмотр кодов", callback_data="admin_view_codes"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_system_stats"),
            ],
        ]
    )
    await callback.message.edit_text(
        "👑 Панель администратора:\n\nВыберите действие:", reply_markup=keyboard
    )
    await callback.answer()
