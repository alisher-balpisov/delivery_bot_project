from dataclasses import dataclass

ERROR_PREFIX = "❌"


@dataclass(frozen=True)
class ErrorCategory:
    """Базовый класс для категорий ошибок, обеспечивающий безопасное форматирование."""

    @staticmethod
    def format_message(template: str, **kwargs) -> str:
        """
        Безопасное форматирование сообщения с fallback для отсутствующих placeholders.
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # Обработка отсутствующих ключей в шаблоне
            missing = str(e).strip("'")
            # Если в сообщении об ошибке не хватает 'detail' или 'error',
            # заменяем их на "нет данных" для предотвращения сбоя.
            if "detail" in missing or "error" in missing:
                return template.replace(f"{{{missing}}}", "нет данных")
            # В противном случае, это ошибка в коде, и мы должны ее увидеть
            raise ValueError(f"Отсутствует обязательный параметр для шаблона ошибки: {missing}")


# Вспомогательные функции для форматирования конкретных типов ошибок
def format_api_error(**kwargs) -> str:
    return ErrorCategory.format_message(ERROR_PREFIX + " Ошибка API: {detail}", **kwargs)


def format_connection_error(**kwargs) -> str:
    return ErrorCategory.format_message(
        ERROR_PREFIX + " Ошибка подключения к API: {error}", **kwargs
    )


def format_code_creation_error(**kwargs) -> str:
    return ErrorCategory.format_message(ERROR_PREFIX + " Ошибка создания кода: {detail}", **kwargs)


def format_code_detail_error(**kwargs) -> str:
    return ErrorCategory.format_message(
        ERROR_PREFIX + " Ошибка: {detail}. Пожалуйста, проверьте код и попробуйте снова.",
        **kwargs,
    )


def format_stats_error(**kwargs) -> str:
    return ErrorCategory.format_message(
        ERROR_PREFIX + " Ошибка получения статистики: {detail}", **kwargs
    )


def format_order_creation_error(**kwargs) -> str:
    return ErrorCategory.format_message(ERROR_PREFIX + " Ошибка создания заказа: {error}", **kwargs)


def format_order_accept_error(**kwargs) -> str:
    return ErrorCategory.format_message(
        ERROR_PREFIX + " Не удалось принять заказ: {error}", **kwargs
    )


class ErrorMessages:
    """
    Централизованный класс для хранения всех констант сообщений об ошибках.
    Сообщения сгруппированы по категориям для удобства доступа.
    """

    class Auth(ErrorCategory):
        """Ошибки, связанные с аутентификацией и авторизацией."""

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
        TOO_MANY_ATTEMPTS = (
            ERROR_PREFIX + " Превышено количество попыток регистрации. Попробуйте позже."
        )
        REGISTRATION_ERROR = ERROR_PREFIX + " Произошла критическая ошибка при регистрации."

    class Network(ErrorCategory):
        """Ошибки, связанные с сетью и подключением."""

        SERVER_ERROR = ERROR_PREFIX + " Произошла ошибка сервера. Попробуйте позже"
        NETWORK_ERROR = ERROR_PREFIX + " Ошибка соединения. Проверьте подключение к интернету"
        NOT_FOUND = ERROR_PREFIX + " Запрошенный ресурс не найден"
        INVALID_INPUT = ERROR_PREFIX + " Некорректные данные. Проверьте ввод и попробуйте снова"
        INTERNAL_ERROR = ERROR_PREFIX + " Произошла внутренняя ошибка."

    class API(ErrorCategory):
        """Ошибки, связанные с взаимодействием с API."""

        API_ERROR = format_api_error
        CONNECTION_ERROR = format_connection_error
        UNEXPECTED_ERROR = ERROR_PREFIX + " Произошла непредвиденная ошибка."
        TIMEOUT_ERROR = ERROR_PREFIX + " Превышено время ожидания"
        NETWORK_CLIENT_ERROR = ERROR_PREFIX + " Ошибка сети"

    class UserData(ErrorCategory):
        """Ошибки, связанные с данными пользователя."""

        USER_DATA_ERROR = ERROR_PREFIX + " Ошибка: данные пользователя недоступны."
        MESSAGE_ERROR = ERROR_PREFIX + " Ошибка: сообщение недоступно."
        INVALID_ROLE = ERROR_PREFIX + " Неверная роль."

    class Menu(ErrorCategory):
        """Ошибки, связанные с меню и навигацией."""

        MENU_ERROR = ERROR_PREFIX + " Произошла ошибка. Попробуйте /help"
        MENU_LOAD_ERROR = ERROR_PREFIX + " Ошибка при загрузке меню"

    class Access(ErrorCategory):
        """Ошибки, связанные с правами доступа."""

        ACCESS_DENIED_GENERAL = ERROR_PREFIX + " Доступ запрещен."
        ACCESS_DENIED_SHOPS_COURIERS = (
            ERROR_PREFIX + " Доступ запрещен. Только магазины и курьеры могут открывать споры."
        )
        ACCESS_DENIED_ADMINS = (
            ERROR_PREFIX + " Доступ запрещен. Только администраторы могут использовать эту команду."
        )
        ROLE_NOT_DEFINED = ERROR_PREFIX + " Роль пользователя не определена."
        INSUFFICIENT_ROLE = ERROR_PREFIX + " У вас недостаточно прав для выполнения этого действия."

    class Disputes(ErrorCategory):
        """Ошибки, связанные со спорами."""

        DISPUTES_LOAD_ERROR = ERROR_PREFIX + " Ошибка при загрузке споров."

    class Codes(ErrorCategory):
        """Ошибки, связанные с кодами регистрации."""

        CODE_CREATION_ERROR = format_code_creation_error
        CODES_RETRIEVAL_ERROR = ERROR_PREFIX + " Не удалось получить коды."
        CODE_DETAIL_ERROR = format_code_detail_error

    class Stats(ErrorCategory):
        """Ошибки, связанные со статистикой."""

        STATS_ERROR = format_stats_error
        STATS_RETRIEVAL_ERROR = ERROR_PREFIX + " Не удалось получить статистику."

    class Orders(ErrorCategory):
        """Ошибки, связанные с заказами."""

        GENERAL_ERROR = ERROR_PREFIX + " Произошла ошибка. Попробуйте позже."
        SHOPS_ONLY = ERROR_PREFIX + " Только магазины могут создавать заказы."
        INVALID_PRICE = ERROR_PREFIX + " Цена должна быть больше 0. Попробуйте еще раз:"
        PRICE_FORMAT_ERROR = ERROR_PREFIX + " Введите корректную цену (число):"
        ORDER_CREATION_ERROR = format_order_creation_error
        ORDER_CANCELLED = ERROR_PREFIX + " Создание заказа отменено."
        COURIERS_ONLY = ERROR_PREFIX + " Только курьеры могут просматривать доступные заказы."
        ORDER_ACCEPT_ERROR = format_order_accept_error
        NO_ORDERS_FOUND = ERROR_PREFIX + " Доступные заказы не найдены для вашей роли."

    # Общие и критические ошибки
    CRITICAL_ERROR = ERROR_PREFIX + " Критическая ошибка"
