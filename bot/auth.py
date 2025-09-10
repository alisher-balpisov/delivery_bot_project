"""
Логика авторизации и регистрации для Telegram бота.
"""

import base64
import hashlib
import os

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.markdown import hbold, hcode
from backend.src.core.config import settings
from backend.src.core.logging import get_logger

from bot.client_manager import client_manager
from bot.constants import UserRole

logger = get_logger(__name__)


def generate_fernet_key() -> str:
    """
    Генерирует или валидирует ключ для Fernet шифрования.
    В production среде требует наличия переменной BOT_ENCRYPTION_KEY.
    """
    env_key = os.getenv("BOT_ENCRYPTION_KEY")
    if env_key:
        try:
            decoded_key = base64.urlsafe_b64decode(env_key)
            if len(decoded_key) == 32:
                logger.info("✅ Используется ключ шифрования из BOT_ENCRYPTION_KEY.")
                return env_key
            logger.warning(
                f"⚠️ Неверный размер ключа в BOT_ENCRYPTION_KEY: {len(decoded_key)} байт вместо 32."
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Ошибка при обработке BOT_ENCRYPTION_KEY: {e}. Генерирую новый ключ.")

    # ИСПРАВЛЕНО: В production среде генерация ключа "на лету" запрещена
    if settings.is_production:
        logger.error("💥 В production среде переменная BOT_ENCRYPTION_KEY должна быть установлена.")
        raise ValueError("BOT_ENCRYPTION_KEY не установлен или некорректен.")

    base_secret = getattr(settings, "secret_key", "default_secret_key_for_bot_auth")
    hashed = hashlib.sha256(base_secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(hashed[:32]).decode("utf-8")
    logger.warning(
        "🔑 Сгенерирован временный ключ шифрования. Для production установите BOT_ENCRYPTION_KEY."
    )
    return key


class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""

    waiting_for_code = State()


# Публичный роутер
auth_router = Router(name="auth_router")

# Защищенный роутер. Middleware будет применен к нему в main.py
protected_router = Router(name="protected_auth_router")
protected_router.message.filter(F.chat.type == "private")
protected_router.callback_query.filter(F.message.chat.type == "private")


@auth_router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    """Обработчик команды /start, выполняет авторизацию пользователя."""
    telegram_id = message.from_user.id
    loading_msg = await message.answer("🔄 Авторизуюсь...")

    try:
        auth_data = await client_manager.auth.bot_login(telegram_id)
        await loading_msg.delete()

        if auth_data:
            await state.update_data(**auth_data)
            role_emoji = {UserRole.ADMIN: "👑", UserRole.SHOP: "🏪", UserRole.COURIER: "🏍️"}.get(
                auth_data.get("role"), "👤"
            )
            text = (
                f"✅ Авторизация успешна {role_emoji}\n\n"
                f"👤 Роль: {hbold(auth_data.get('role', 'неизвестна').upper())}\n"
                "Используйте /help для просмотра доступных команд."
            )
        else:
            text = "❌ Вы не зарегистрированы.\n\nПолучите код у администратора и используйте команду /register."
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}", exc_info=True)
        await loading_msg.delete()
        await message.answer("❌ Произошла ошибка авторизации. Попробуйте позже.")


@auth_router.message(Command("register"))
async def register_handler(message: Message, state: FSMContext, user_data: dict):
    """Начинает процесс регистрации пользователя по коду."""
    if user_data.get("access_token"):
        await message.answer("✅ Вы уже авторизованы. Для смены аккаунта используйте /logout.")
        return

    await state.set_state(RegistrationStates.waiting_for_code)
    await message.answer("📝 Введите ваш код приглашения:")


@auth_router.message(RegistrationStates.waiting_for_code)
async def register_code_handler(message: Message, state: FSMContext):
    """Обрабатывает введенный пользователем код регистрации."""
    code = message.text.strip()
    if not code:
        await message.answer("❌ Код не может быть пустым. Попробуйте еще раз.")
        return

    loading_msg = await message.answer("🔄 Проверяю код...")
    try:
        result = await client_manager.auth.register_user(message.from_user.id, code)
        await loading_msg.delete()

        if result and result.get("success"):
            role_emoji = {UserRole.ADMIN: "👑", UserRole.SHOP: "🏪", UserRole.COURIER: "🏍️"}.get(
                result.get("role"), "👤"
            )
            text = f"✅ Регистрация успешна {role_emoji}\nТеперь используйте /start для входа в систему."
            await state.clear()
        else:
            detail = result.get("detail", "Неизвестная ошибка") if result else "Неизвестная ошибка"
            text = f"❌ Ошибка: {detail}. Пожалуйста, проверьте код и попробуйте снова."
            # Состояние не сбрасываем, чтобы дать пользователю еще попытку
            await state.set_state(RegistrationStates.waiting_for_code)

        await message.answer(text)
    except Exception as e:
        logger.error(f"Критическая ошибка при регистрации: {e}", exc_info=True)
        await loading_msg.delete()
        await state.clear()
        await message.answer("❌ Произошла критическая ошибка при регистрации.")


@protected_router.message(Command("logout"))
async def logout_handler(message: Message, state: FSMContext):
    """Выход из системы и очистка состояния."""
    await state.clear()
    logger.info(f"Пользователь {message.from_user.id} вышел из системы.")
    await message.answer("👋 Вы вышли из системы.\nИспользуйте /start для повторной авторизации.")


@protected_router.message(Command("me"))
async def me_handler(message: Message, user_data: dict):
    """Показывает информацию о текущем пользователе."""
    user = user_data.get("user", {})
    print(user_data.get("role"), "<-----")
    text_parts = [
        hbold("👤 Ваш профиль:"),
        f"  - ID в Telegram: {hcode(message.from_user.id)}",
        f"  - Роль: {hbold(user_data.get('role', 'неизвестна').upper())}",
        f"  - Имя: {user.get('name', 'не указано')}",
        "  - Статус: Авторизован",
    ]
    await message.answer("\n".join(text_parts), parse_mode=ParseMode.HTML)
