"""Валидаторы данных профиля магазина."""

import re


def validate_shop_name(name: str) -> tuple[bool, str | None]:
    """Валидирует название магазина."""
    name = name.strip()

    if len(name) < 3:
        return False, "Название слишком короткое. Минимум 3 символа."

    if len(name) > 100:
        return False, "Название слишком длинное. Максимум 100 символов."

    return True, None


def validate_shop_address(address: str) -> tuple[bool, str | None]:
    """Валидирует адрес магазина."""
    address = address.strip()

    if len(address) < 10:
        return False, "Адрес слишком короткий. Минимум 10 символов."

    if len(address) > 200:
        return False, "Адрес слишком длинный. Максимум 200 символов."

    return True, None


def validate_phone_number(phone: str) -> tuple[str | None, str | None]:
    """
    Валидирует и нормализует номер телефона.

    Returns:
        Tuple(нормализованный номер или None, ошибка или None)
    """
    # Удаляем все кроме цифр и +
    normalized = re.sub(r"[^\d+]", "", phone.strip())

    # Проверяем количество цифр
    digits_only = re.sub(r"[^\d]", "", normalized)

    if len(digits_only) < 10 or len(digits_only) > 20:
        return None, (
            "Неверный формат номера телефона. Используйте формат: +77012345678 или 87012345678"
        )

    return normalized, None
