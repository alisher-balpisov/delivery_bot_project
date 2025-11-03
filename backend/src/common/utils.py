import re
from typing import Annotated

from pydantic import PlainValidator


def validate_phone(v):
    if not isinstance(v, str):
        raise ValueError("Телефон должен быть строкой")
    if not v.startswith("+"):
        raise ValueError("Телефон должен начинаться с +")
    # Проверка международного формата: +{код страны}{номер} (7-15 цифр после +)
    if not re.match(r"^\+[1-9]\d{7,15}$", v):
        raise ValueError(
            "Некорректный формат телефона (должен быть в международном формате, например +71234567890)"
        )
    return v


def validate_phone_flexible(v):
    """Валидация телефона, принимающая любой формат"""
    if not isinstance(v, str):
        raise ValueError("Телефон должен быть строкой")
    # Удаляем все пробелы для базовой проверки
    cleaned = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    # Должен содержать хотя бы 7 цифр
    digits = re.findall(r"\d", cleaned)
    if len(digits) < 7:
        raise ValueError("Телефон должен содержать минимум 7 цифр")
    if len(v.strip()) == 0:
        raise ValueError("Телефон не может быть пустым")
    return v.strip()


Phone = Annotated[str, PlainValidator(validate_phone)]
PhoneFlexible = Annotated[str, PlainValidator(validate_phone_flexible)]
