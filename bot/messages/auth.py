"""
Модуль сообщений для аутентификации и регистрации.
"""

from typing import Final


class AuthMessages:
    """Сообщения для процесса аутентификации и регистрации."""

    WELCOME_NEW_USER: Final = (
        "Добро пожаловать! Для начала работы получите код у администратора "
        "и используйте команду /register"
    )

    WELCOME_ADMIN: Final = (
        "Добро пожаловать, администратор!\n"
        "Используйте /admin для доступа к панели или /help для списка команд."
    )

    WELCOME_AUTHENTICATED: Final = (
        "Добро пожаловать! Вы успешно авторизованы ✅\n"
        "Используйте /help для просмотра доступных команд."
    )

    ENTER_CODE: Final = "📝 Введите ваш код приглашения:"

    CHECKING_CODE: Final = "🔄 Проверяю код..."

    ALREADY_REGISTERED: Final = "ℹ️ Вы уже зарегистрированы. Используйте /help для просмотра команд."

    SUCCESS: Final = "✅ Регистрация успешна!\nНажмите /start, чтобы обновить меню."

    BLOCKED: Final = (
        "❌ Превышено количество попыток ввода кода. Пожалуйста, попробуйте снова через 15 минут."
    )

    INVALID_CODE_ATTEMPTS: Final = "Неверный код. Осталось попыток: {attempts}"

    INVALID_CODE: Final = "Неверный код или он уже был использован. Попробуйте еще раз."

    LOGOUT_SUCCESS: Final = "✅ Вы успешно вышли из системы. Для входа используйте /start."

    NOT_LOGGED_IN: Final = "Вы не авторизованы. Используйте /start для начала работы."

    ME_STATS_TEMPLATE: Final = (
        "📈 **Ваш профиль:**\n\n"
        "🆔 ID пользователя: {id}\n"
        "👤 Имя: {name}\n"
        "{emoji} Роль: {role}\n"
        "📱 Telegram ID: {telegram_id}\n"
        "✨ Статус: {status}\n"
        "🚫 Блокировка: {is_blocked}"
    )


class AuthService:
    """Служебные сообщения для аутентификации."""

    UNKNOWN_ROLE: Final = "Получена неизвестная роль '{}' от API. Присвоена роль GUEST."
    STATE_UPDATED: Final = "Обновлены данные в FSM для пользователя {}"
    UNKNOWN_ERROR: Final = "Неизвестная ошибка"
    ACTIVE: Final = "активен"
    DEACTIVATED: Final = "деактивирован"
    YES: Final = "да"
    NO: Final = "нет"
    NOT_SPECIFIED: Final = "не указано"
    UNEXPECTED_ERROR: Final = "Неожиданная ошибка в get_user_stats_text: {}"
    REGISTRATION_CRITICAL_ERROR: Final = "Критическая ошибка при регистрации {}"
    GENERIC_ERROR: Final = "Произошла ошибка. Попробуйте перезапустить бота командой /start."
    CRITICAL_REGISTRATION_ERROR: Final = "Произошла критическая ошибка при регистрации."
    TOKEN_FETCH_ERROR: Final = "Не удалось получить или обновить токен доступа."
