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


Phone = Annotated[str, PlainValidator(validate_phone)]
