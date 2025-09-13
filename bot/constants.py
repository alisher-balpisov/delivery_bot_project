from dataclasses import dataclass

from backend.src.common.enums import UserRole

MAX_REGISTRATION_ATTEMPTS = 5

ROLE_EMOJI_MAP = {
    "admin": "👑",
    "shop": "🏪",
    "courier": "🏍️",
    "guest": "👤",
    "pending": "👤",
}


# Команды по ролям
ROLE_COMMANDS: dict[str, dict[str, any]] = {
    UserRole.ADMIN.value: {
        "icon": "👑",
        "title": "Администратор:",
        "commands": [
            "/admin - управление системой\n",
            "/stats - полная статистика\n",
            "/disputes - управление спорами\n",
            "/broadcast - массовая рассылка",
        ],
    },
    UserRole.SHOP.value: {
        "icon": "🏪",
        "title": "Магазин:",
        "commands": [
            "/new_order - создать заказ\n",
            "/my_orders - мои заказы\n",
            "/order_history - история заказов\n",
            "/dispute - открыть спор",
        ],
    },
    UserRole.COURIER.value: {
        "icon": "🏍️",
        "title": "Курьер:",
        "commands": [
            "/available_orders - доступные заказы\n",
            "/my_orders - активные доставки\n",
            "/earnings - мои заработки\n",
            "/rating - мой рейтинг",
        ],
    },
}


ERROR_PREFIX = "❌"


@dataclass(frozen=True)
class ErrorCategory:
    @staticmethod
    def format_message(template: str, **kwargs):
        """Безопасное форматирование сообщения с fallback для отсутствующих placeholders."""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # Обработка missing keys
            missing = str(e).strip("'").replace("'", "")
            if "detail" in missing or "error" in missing:
                return template.replace(f"{{{missing}}}", "нет данных")
            raise ValueError(f"Missing required parameter for error template: {missing}")


# Вспомогательные функции для форматирования ошибок
def format_api_error(**kwargs):
    return ErrorCategory.format_message(ERROR_PREFIX + " Ошибка API: {detail}", **kwargs)


def format_connection_error(**kwargs):
    return ErrorCategory.format_message(
        ERROR_PREFIX + " Ошибка подключения к API: {error}", **kwargs
    )


def format_code_creation_error(**kwargs):
    return ErrorCategory.format_message(ERROR_PREFIX + " Ошибка создания кода: {detail}", **kwargs)


def format_code_detail_error(**kwargs):
    return ErrorCategory.format_message(
        ERROR_PREFIX + " Ошибка: {detail}. Пожалуйста, проверьте код и попробуйте снова.",
        **kwargs,
    )


def format_stats_error(**kwargs):
    return ErrorCategory.format_message(
        ERROR_PREFIX + " Ошибка получения статистики: {detail}", **kwargs
    )


def format_order_creation_error(**kwargs):
    return ErrorCategory.format_message(ERROR_PREFIX + " Ошибка создания заказа: {error}", **kwargs)


def format_order_accept_error(**kwargs):
    return ErrorCategory.format_message(
        ERROR_PREFIX + " Не удалось принять заказ: {error}", **kwargs
    )


class ErrorMessages:
    """Константы сообщений об ошибок.

    Используйте ErrorMessages.Auth.UNAUTHORIZED для доступа.
    Все сообщения immutable для производительности.
    """

    class Auth(ErrorCategory):
        """Ошибки авторизации."""

        UNAUTHORIZED = ERROR_PREFIX + " Сначала авторизуйтесь с помощью /start"
        FORBIDDEN = ERROR_PREFIX + " У вас нет прав для выполнения этого действия"
        NOT_REGISTERED = (
            ERROR_PREFIX
            + " Вы не зарегистрированы.\n\nПолучите код у администратора и используйте команду /register."
        )
        AUTH_ERROR = ERROR_PREFIX + " Произошла ошибка авторизации. Попробуйте позже."
        EMPTY_CODE = ERROR_PREFIX + " Код не может быть пустым. Попробуйте еще раз."
        CODE_LENGTH_INVALID = ERROR_PREFIX + " Код должен быть от 4 до 20 символов."
        CODE_CONTAINS_INVALID_CHARS = ERROR_PREFIX + " Код должен содержать только буквы и цифры."
        TOO_MANY_ATTEMPTS = ERROR_PREFIX + " Превышено количество попыток регистрации. Попробуйте позже."
        REGISTRATION_ERROR = ERROR_PREFIX + " Произошла критическая ошибка при регистрации."
        INVALID_TOKEN = ERROR_PREFIX + " Токен недействителен. Авторизуйтесь заново: /start"

    class Network(ErrorCategory):
        """Сетевые ошибки."""

        SERVER_ERROR = ERROR_PREFIX + " Произошла ошибка сервера. Попробуйте позже"
        NETWORK_ERROR = ERROR_PREFIX + " Ошибка соединения. Проверьте подключение к интернету"
        NOT_FOUND = ERROR_PREFIX + " Запрошенный ресурс не найден"
        INVALID_INPUT = ERROR_PREFIX + " Некорректные данные. Проверьте ввод и попробуйте снова"

    class API(ErrorCategory):
        """Ошибки API."""

        API_ERROR = format_api_error
        CONNECTION_ERROR = format_connection_error
        UNEXPECTED_ERROR = ERROR_PREFIX + " Произошла непредвиденная ошибка."
        TIMEOUT_ERROR = ERROR_PREFIX + " Превышено время ожидания"
        NETWORK_CLIENT_ERROR = ERROR_PREFIX + " Ошибка сети"

    class UserData(ErrorCategory):
        """Ошибки данных пользователя."""

        USER_DATA_ERROR = ERROR_PREFIX + " Ошибка: данные пользователя недоступны."
        MESSAGE_ERROR = ERROR_PREFIX + " Ошибка: сообщение недоступно."
        INVALID_ROLE = ERROR_PREFIX + " Неверная роль."

    class Menu(ErrorCategory):
        """Ошибки меню."""

        MENU_ERROR = ERROR_PREFIX + " Произошла ошибка. Попробуйте /help"
        MENU_LOAD_ERROR = ERROR_PREFIX + " Ошибка при загрузке меню"

    class Access(ErrorCategory):
        """Ошибки доступа."""

        ACCESS_DENIED_GENERAL = ERROR_PREFIX + " Доступ запрещен."
        ACCESS_DENIED_SHOPS_COURIERS = (
            ERROR_PREFIX + " Доступ запрещен. Только магазины и курьеры могут открывать споры."
        )
        ACCESS_DENIED_ADMINS = (
            ERROR_PREFIX + " Доступ запрещен. Только администраторы могут использовать эту команду."
        )

    class Disputes(ErrorCategory):
        """Ошибки споров."""

        DISPUTES_LOAD_ERROR = ERROR_PREFIX + " Ошибка при загрузке споров."

    class Codes(ErrorCategory):
        """Ошибки кодов."""

        CODE_CREATION_ERROR = format_code_creation_error

        CODES_RETRIEVAL_ERROR = ERROR_PREFIX + " Не удалось получить коды."

        CODE_DETAIL_ERROR = format_code_detail_error

    class Stats(ErrorCategory):
        """Ошибки статистики."""

        STATS_ERROR = format_stats_error
        STATS_RETRIEVAL_ERROR = ERROR_PREFIX + " Не удалось получить статистику."

    class Orders(ErrorCategory):
        """Ошибки заказов."""

        GENERAL_ERROR = ERROR_PREFIX + " Произошла ошибка. Попробуйте позже."
        SHOPS_ONLY = ERROR_PREFIX + " Только магазины могут создавать заказы."
        INVALID_PRICE = ERROR_PREFIX + " Цена должна быть больше 0. Попробуйте еще раз:"
        PRICE_FORMAT_ERROR = ERROR_PREFIX + " Введите корректную цену (число):"

        ORDER_CREATION_ERROR = format_order_creation_error

        ORDER_CANCELLED = ERROR_PREFIX + " Создание заказа отменено."
        COURIERS_ONLY = ERROR_PREFIX + " Только курьеры могут просматривать доступные заказы."

        ORDER_ACCEPT_ERROR = format_order_accept_error

        NO_ORDERS_FOUND = ERROR_PREFIX + " Доступные заказы не найдены для вашей роли."

    CRITICAL_ERROR = ERROR_PREFIX + " Критическая ошибка"
