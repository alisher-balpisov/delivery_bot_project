"""
Обработчики команд и сообщений для Telegram бота
"""

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.core.logging import get_logger

from bot.client_manager import client_manager

logger = get_logger(__name__)

# ИСПРАВЛЕНО: Роутеры разделены на публичные и защищенные
# Публичный роутер (команды типа /help, /start)
public_router = Router(name="public_handlers")
# Защищенный роутер (требует авторизации)
protected_router = Router(name="protected_handlers")


ROLE_COMMANDS: dict[str, dict[str, str]] = {
    "admin": {
        "icon": "👑",
        "title": "Администратор:",
        "commands": [
            "/admin - управление системой\n",
        ],
    },
    "shop": {"icon": "🏪", "title": "Магазин:", "commands": ["/orders - мои заказы\n"]},
    "courier": {"icon": "🏍️", "title": "Курьер:", "commands": ["/orders - назначенные заказы\n"]},
}


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


@protected_router.callback_query(F.data == "show_menu")
async def show_menu_callback(callback: CallbackQuery, user_data: dict):
    """Показать меню команд (через callback, требует авторизации)."""
    role = user_data.get("role", "guest")
    text = "🏠 Главное меню:\n\n"
    # ... (логика генерации меню)
    await callback.message.edit_text(text)
    await callback.answer()


def generate_help_text(role: str) -> str:
    """Генерация текста справки по командам в зависимости от роли."""
    help_text = "🤖 Справка по командам:\n\n"
    help_text += "📋 Основные:\n"
    help_text += "/start - Авторизация\n"
    help_text += "/register - Регистрация\n"
    help_text += "/help - Эта справка\n"

    if role != "guest":
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
    role = user_data.get("role", "guest")
    await message.answer(generate_help_text(role))


@protected_router.message(Command("orders"))
async def orders_handler(message: Message, user_data: dict):
    """Показать заказы в зависимости от роли (требует авторизации)."""
    role = user_data.get("role", "unknown")
    if role == "shop":
        await message.answer("🏪 Ваши заказы:\n\n📦 Создайте новый заказ командой /new_order")
    elif role == "courier":
        await message.answer("🏍️ Назначенные заказы:\n\n🚚 Доступные заказы появятся здесь")
    elif role == "admin":
        await message.answer(
            "👑 Управление заказами:\n\n⚙️ Все заказы системы доступны в панели администратора"
        )
    else:
        await message.answer("❓ Доступные заказы не найдены для вашей роли.")


@protected_router.message(Command("admin"))
async def admin_handler(message: Message, user_data: dict):
    """Показать панель администратора (требует авторизации и роли admin)."""
    role = user_data.get("role", "guest")
    if role != "admin":
        await message.answer(
            "❌ Доступ запрещен. Только администраторы могут использовать эту команду."
        )
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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


@protected_router.callback_query(F.data.startswith("admin_"))
async def admin_callback_handler(callback: CallbackQuery, user_data: dict):
    """Обработчик callback для админских функций."""
    data = callback.data
    token = user_data.get("access_token")

    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
            if role not in ["shop", "courier"]:
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
                text = f"📊 Системная статистика:\n\n"
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
    role = user_data.get("role", "guest")
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


async def admin_handler(message: Message, user_data: dict):
    """Показать панель администратора (требует авторизации и роли admin)."""
    role = user_data.get("role", "guest")
    if role != "admin":
        await message.answer(
            "❌ Доступ запрещен. Только администраторы могут использовать эту команду."
        )
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
            if role not in ["shop", "courier"]:
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
                for code_info in codes[:10]:  # Ограничим до 10 для длинны сообщения
                    text += f"Код: `{code_info.get('code', '?')}` Роль: {code_info.get('role', '?')} Статус: {'использован' if code_info.get('is_used') else 'активен'}\n"
                if len(codes) > 10:
                    text += f"\n... и ещё {len(codes) - 10} кодов"
                await callback.message.edit_text(text, parse_mode="Markdown")
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
                text = f"📊 Системная статистика:\n\n"
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


async def admin_back_to_menu(callback: CallbackQuery):
    """Вернуться в главное меню админа."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
