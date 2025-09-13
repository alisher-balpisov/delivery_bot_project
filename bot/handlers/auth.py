import base64
import hashlib
import os

import httpx
from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.markdown import hbold, hcode
from backend.src.core.config import settings
from backend.src.core.logging import get_logger

from bot.clients import client_manager
from bot.constants import ROLE_EMOJI_MAP, ErrorMessages

logger = get_logger(__name__)


def generate_fernet_key() -> str:
    """
    Генерирует или валидирует ключ для Fernet шифрования.
    Требует наличия переменной окружения BOT_ENCRYPTION_KEY.
    """
    env_key = os.getenv("BOT_ENCRYPTION_KEY")
    if not env_key:
        logger.critical("💥 Переменная окружения BOT_ENCRYPTION_KEY не установлена!")
        raise ValueError("BOT_ENCRYPTION_KEY должна быть установлена.")

    try:
        # Валидация ключа
        decoded_key = base64.urlsafe_b64decode(env_key)
        if len(decoded_key) == 32:
            logger.info("✅ Используется ключ шифрования из BOT_ENCRYPTION_KEY.")
            return env_key
        raise ValueError("Неверный размер ключа в BOT_ENCRYPTION_KEY (требуется 32 байта).")
    except Exception as e:
        logger.critical(f"Ошибка валидации ключа шифрования: {e}")
        raise


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
            role_emoji = ROLE_EMOJI_MAP.get(auth_data.get("role"), "👤")
            text = (
                f"✅ Авторизация успешна {role_emoji}\n\n"
                f"👤 Роль: {hbold(auth_data.get('role', 'неизвестна').upper())}\n"
                "Используйте /help для просмотра доступных команд."
            )
        else:
            text = ErrorMessages.Auth.NOT_REGISTERED
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}", exc_info=True)
        await loading_msg.delete()
        await message.answer(ErrorMessages.Auth.AUTH_ERROR)


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
    """Обрабатывает введенный код регистрации с улучшенной валидацией и обработкой."""
    telegram_id = message.from_user.id
    code = message.text.strip() if message.text else ""

    # Показываем сообщение загрузки
    loading_msg = await message.answer("🔄 Проверяю код...")

    try:
        result = await client_manager.auth.register_user(telegram_id, code)
        await loading_msg.delete()

        if result and result.get("success"):
            await _handle_successful_registration(message, result, state)
        else:
            await _handle_registration_failure(message, result, state)

    except httpx.HTTPStatusError as e:
        # Обработка HTTP ошибок
        await loading_msg.delete()
        logger.warning(f"HTTP ошибка при регистрации для {telegram_id}: {e}")
        detail = "Ошибка сервера" if e.response.status_code >= 500 else "Неверный запрос"
        await _handle_registration_failure(message, {"success": False, "detail": detail}, state)

    except httpx.TimeoutException:
        # Обработка таймаута
        await loading_msg.delete()
        logger.warning(f"Таймаут при регистрации для {telegram_id}")
        await message.answer("⏰ Превышено время ожидания ответа сервера. Попробуйте позже.")
        # Не сбрасываем состояние, даем попытку позже

    except httpx.RequestError as e:
        # Обработка сетевых ошибок
        await loading_msg.delete()
        logger.warning(f"Сетевая ошибка при регистрации для {telegram_id}: {e}")
        await message.answer(ErrorMessages.Network.NETWORK_ERROR)
        # Не сбрасываем состояние, даем попытку позже

    except Exception as e:
        await loading_msg.delete()
        logger.error(
            f"Критическая ошибка при регистрации пользователя {telegram_id} с кодом: {e}",
            exc_info=True,
        )
        await state.clear()
        await message.answer(ErrorMessages.Auth.REGISTRATION_ERROR)


async def _handle_successful_registration(message: Message, result: dict, state: FSMContext):
    """Обрабатывает успешную регистрацию."""
    role_emoji = ROLE_EMOJI_MAP.get(result.get("role"), "👤")
    text = f"✅ Регистрация успешна {role_emoji}\nТеперь используйте /start для входа в систему."
    await message.answer(text)
    await state.clear()


async def _handle_registration_failure(message: Message, result: dict, state: FSMContext):
    """Обрабатывает неудачную регистрацию."""
    detail = result.get("detail", "Неизвестная ошибка") if result else "Неизвестная ошибка"
    text = ErrorMessages.Codes.CODE_DETAIL_ERROR(detail=detail)
    await message.answer(text)


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
    # ИСПРАВЛЕНО: Удалена отладочная печать
    text_parts = [
        hbold("👤 Ваш профиль:"),
        f"  - ID в Telegram: {hcode(message.from_user.id)}",
        f"  - Роль: {hbold(user_data.get('role', 'неизвестна').upper())}",
        f"  - Имя: {user.get('name', 'не указано')}",
        "  - Статус: Авторизован",
    ]
    await message.answer("\n".join(text_parts), parse_mode=ParseMode.HTML)
