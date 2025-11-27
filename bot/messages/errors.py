"""
Модуль сообщений об ошибках.
"""

from typing import Final


class ErrorMessages:
    """Централизованные сообщения об ошибках."""

    # Префикс для всех ошибок
    PREFIX: Final = "❌"

    class Auth:
        """Ошибки аутентификации."""

        UNAUTHORIZED: Final = "❌ Сначала авторизуйтесь с помощью /start"
        FORBIDDEN: Final = "❌ У вас нет прав для выполнения этого действия"
        NOT_REGISTERED: Final = (
            "❌ Вы не зарегистрированы.\n\n"
            "Получите код у администратора и используйте команду /register."
        )
        AUTH_ERROR: Final = "❌ Произошла ошибка авторизации. Попробуйте позже."
        EMPTY_CODE: Final = "❌ Код не может быть пустым. Попробуйте еще раз."
        CODE_LENGTH_INVALID: Final = "❌ Код должен быть от 4 до 20 символов."
        CODE_CONTAINS_INVALID_CHARS: Final = "❌ Код должен содержать только буквы и цифры."
        TOO_MANY_ATTEMPTS: Final = "❌ Превышено количество попыток регистрации. Попробуйте позже."
        REGISTRATION_ERROR: Final = "❌ Произошла критическая ошибка при регистрации."

    class Network:
        """Сетевые ошибки."""

        SERVER_ERROR: Final = "❌ Произошла ошибка сервера. Попробуйте позже"
        NETWORK_ERROR: Final = "❌ Ошибка соединения. Проверьте подключение к интернету"
        NOT_FOUND: Final = "❌ Запрошенный ресурс не найден"
        INVALID_INPUT: Final = "❌ Некорректные данные. Проверьте ввод и попробуйте снова"
        INTERNAL_ERROR: Final = "❌ Произошла внутренняя ошибка."

    class API:
        """Ошибки API."""

        @staticmethod
        def API_ERROR(detail: str) -> str:
            return f"❌ Ошибка API: {detail}"

        @staticmethod
        def CONNECTION_ERROR(error: str) -> str:
            return f"❌ Ошибка подключения к API: {error}"

        UNEXPECTED_ERROR: Final = "❌ Произошла непредвиденная ошибка."
        TIMEOUT_ERROR: Final = "❌ Превышено время ожидания"
        NETWORK_CLIENT_ERROR: Final = "❌ Ошибка сети"

    class Access:
        """Ошибки доступа."""

        ACCESS_DENIED_GENERAL: Final = "❌ Доступ запрещен."
        ACCESS_DENIED_SHOPS_COURIERS: Final = (
            "❌ Доступ запрещен. Только магазины и курьеры могут открывать споры."
        )
        ACCESS_DENIED_ADMINS: Final = (
            "❌ Доступ запрещен. Только администраторы могут использовать эту команду."
        )
        ROLE_NOT_DEFINED: Final = "❌ Роль пользователя не определена."
        INSUFFICIENT_ROLE: Final = "❌ У вас недостаточно прав для выполнения этого действия."


class BaseClientMessages:
    """Сообщения для базового API клиента."""

    INVALID_JSON: Final = "Не удалось распарсить ответ как JSON"
    HTTP_ERROR: Final = "HTTP ошибка {} на {}: {}"
    SERVER_ERROR_RETRY: Final = "Серверная ошибка {} - попытка {} из {}"
    TIMEOUT_RETRY: Final = "Таймаут на {} - попытка {} из {}"
    TIMEOUT_ERROR: Final = "Таймаут при {} {}"
    TIMEOUT_EXCEEDED: Final = "Таймаут превышен"
    NETWORK_ERROR_RETRY: Final = "Сетевая ошибка на {} - попытка {} из {}"
    NETWORK_ERROR: Final = "Сетевая ошибка при {} {}: {}"
    NETWORK_ERROR_SIMPLE: Final = "Сетевая ошибка"
    UNEXPECTED_REQUEST_ERROR: Final = "Неожиданная ошибка запроса при {} {}: {}"
    UNEXPECTED_CLIENT_ERROR: Final = "Неожиданная ошибка клиента"
    RETRIES_EXCEEDED: Final = "Превышено количество попыток"
