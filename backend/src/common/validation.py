"""
Централизованные правила валидации для приложения.

Этот модуль содержит константы валидации, валидаторы для Pydantic схем
и утилиты для проверки бизнес-правил.
"""

from typing import Any, ClassVar

# ==============================================================================
# Константы валидации
# ==============================================================================


class ValidationRules:
    """Константы для валидации данных приложения."""

    # Заказы
    MIN_ORDER_PRICE: int = 100  # минимальная цена заказа в тенге
    MAX_ORDER_PRICE: int = 1000000  # максимальная цена заказа
    MAX_DESCRIPTION_LENGTH: int = 500
    MAX_ADDRESS_LENGTH: int = 200

    # Споры
    DISPUTE_TIME_LIMIT: int = 86400  # 24 часа для открытия спора в секундах

    # Telegram
    MIN_TELEGRAM_ID: int = 1
    MAX_TELEGRAM_ID: int = 2147483647

    # Пагинация
    DEFAULT_PAGE: int = 1
    DEFAULT_LIMIT: int = 10
    MAX_LIMIT: int = 100
    MIN_LIMIT: int = 1

    # Телефоны
    MIN_PHONE_LENGTH: int = 10
    MAX_PHONE_LENGTH: int = 30

    # Пользователи
    MIN_USERNAME_LENGTH: int = 3
    MAX_USERNAME_LENGTH: int = 255
    MAX_REGISTRATION_ATTEMPTS: int = 3

    # Коды регистрации
    MIN_CODE_LENGTH: int = 4
    MAX_CODE_LENGTH: int = 20

    # Имена и тексты
    MIN_NAME_LENGTH: int = 1
    MAX_NAME_LENGTH: int = 255


# Обратная совместимость (deprecated, используйте ValidationRules)
VALIDATION = {
    "min_order_price": float(ValidationRules.MIN_ORDER_PRICE),
    "max_order_price": float(ValidationRules.MAX_ORDER_PRICE),
    "max_description_length": ValidationRules.MAX_DESCRIPTION_LENGTH,
    "max_address_length": ValidationRules.MAX_ADDRESS_LENGTH,
    "dispute_time_limit": ValidationRules.DISPUTE_TIME_LIMIT,
}


# ==============================================================================
# Константы комиссий
# ==============================================================================


class CommissionRules:
    """Правила комиссий и платежей."""

    PLATFORM_FEE_PERCENT: int = 10  # комиссия платформы в процентах
    MIN_COMMISSION: int = 50  # минимальная комиссия в тенге
    PAYMENT_METHODS: ClassVar[list[str]] = ["cash", "card", "kaspi"]


# Обратная совместимость (deprecated, используйте CommissionRules)
COMMISSION: dict[str, Any] = {
    "platform_fee_percent": float(CommissionRules.PLATFORM_FEE_PERCENT),
    "min_commission": float(CommissionRules.MIN_COMMISSION),
    "payment_methods": CommissionRules.PAYMENT_METHODS,
}


# ==============================================================================
# Pydantic валидаторы
# ==============================================================================


def validate_telegram_id(cls, v: int) -> int:
    """
    Валидатор для Telegram ID.

    Args:
        v: Значение для проверки

    Returns:
        Валидированное значение

    Raises:
        ValueError: Если значение вне допустимого диапазона
    """
    if not ValidationRules.MIN_TELEGRAM_ID <= v <= ValidationRules.MAX_TELEGRAM_ID:
        raise ValueError(
            f"Telegram ID должен быть между {ValidationRules.MIN_TELEGRAM_ID} "
            f"и {ValidationRules.MAX_TELEGRAM_ID}"
        )
    return v


def validate_order_price(cls, v: int) -> int:
    """
    Валидатор для цены заказа.

    Args:
        v: Значение для проверки

    Returns:
        Валидированное значение

    Raises:
        ValueError: Если цена вне допустимого диапазона
    """
    if not ValidationRules.MIN_ORDER_PRICE <= v <= ValidationRules.MAX_ORDER_PRICE:
        raise ValueError(
            f"Цена заказа должна быть между {ValidationRules.MIN_ORDER_PRICE} "
            f"и {ValidationRules.MAX_ORDER_PRICE}"
        )
    return v


def validate_non_empty_string(cls, v: str | None, field_name: str = "Поле") -> str | None:
    """
    Валидатор для непустых строк.

    Args:
        v: Значение для проверки
        field_name: Название поля для сообщения об ошибке

    Returns:
        Валидированное значение

    Raises:
        ValueError: Если строка пустая
    """
    if v is not None and not v.strip():
        raise ValueError(f"{field_name} не может быть пустым")
    return v


def validate_phone_number(cls, v: str) -> str:
    """
    Валидатор для номера телефона.

    Args:
        v: Значение для проверки

    Returns:
        Валидированное значение

    Raises:
        ValueError: Если номер некорректен
    """
    if not v or not v.strip():
        raise ValueError("Номер телефона не может быть пустым")

    # Убираем все символы кроме цифр и +
    cleaned = "".join(c for c in v if c.isdigit() or c == "+")

    if not ValidationRules.MIN_PHONE_LENGTH <= len(cleaned) <= ValidationRules.MAX_PHONE_LENGTH:
        raise ValueError(
            f"Номер телефона должен содержать от {ValidationRules.MIN_PHONE_LENGTH} "
            f"до {ValidationRules.MAX_PHONE_LENGTH} цифр"
        )

    return v


def validate_pagination_params(page: int, limit: int) -> tuple[int, int]:
    """
    Валидация параметров пагинации.

    Args:
        page: Номер страницы
        limit: Количество элементов на странице

    Returns:
        Кортеж (page, limit) с валидированными значениями

    Raises:
        ValueError: Если параметры некорректны
    """
    if page < 1:
        raise ValueError("Номер страницы должен быть больше 0")

    if not ValidationRules.MIN_LIMIT <= limit <= ValidationRules.MAX_LIMIT:
        raise ValueError(
            f"Количество элементов должно быть от {ValidationRules.MIN_LIMIT} "
            f"до {ValidationRules.MAX_LIMIT}"
        )

    return page, limit


# ==============================================================================
# Утилиты
# ==============================================================================


def is_valid_price_range(price: int) -> bool:
    """
    Проверка, находится ли цена в допустимом диапазоне.

    Args:
        price: Цена для проверки

    Returns:
        True если цена валидна, иначе False
    """
    return ValidationRules.MIN_ORDER_PRICE <= price <= ValidationRules.MAX_ORDER_PRICE


def calculate_commission(price: int) -> int:
    """
    Расчет комиссии платформы.

    Args:
        price: Цена заказа

    Returns:
        Сумма комиссии
    """
    commission = int(price * CommissionRules.PLATFORM_FEE_PERCENT / 100)
    return max(commission, CommissionRules.MIN_COMMISSION)


def normalize_phone_number(phone: str) -> str:
    """
    Нормализация номера телефона.

    Args:
        phone: Номер телефона

    Returns:
        Нормализованный номер
    """
    # Убираем все символы кроме цифр и +
    return "".join(c for c in phone if c.isdigit() or c == "+")


__all__ = [
    "COMMISSION",  # deprecated
    "VALIDATION",  # deprecated
    "CommissionRules",
    "ValidationRules",
    "calculate_commission",
    "is_valid_price_range",
    "normalize_phone_number",
    "validate_non_empty_string",
    "validate_order_price",
    "validate_pagination_params",
    "validate_phone_number",
    "validate_telegram_id",
]
