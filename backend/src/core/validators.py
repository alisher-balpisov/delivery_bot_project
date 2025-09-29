import re
from typing import Any

from pydantic import ValidationError

# Список подозрительных строковых паттернов
DANGEROUS_PATTERNS_STR = [
    r";\s*--",  # SQL комментарии
    r";\s*/\*",  # Начало SQL блока комментариев
    r"union\s+select",  # UNION SELECT атаки
    r"<\s*script",  # XSS script tags
    r"javascript\s*:",  # JavaScript URI
    r"on\w+\s*=",  # XSS event handlers
    r"<iframe",  # XSS iframe
    r"eval\s*\(",  # JavaScript eval
]

# Скомпилированные паттерны для производительности
# re.IGNORECASE делает проверку нечувствительной к регистру (например, 'SELECT' и 'select')
COMPILED_DANGEROUS_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS_STR]


def validate_no_malicious_content(value: Any) -> Any:
    """
    Валидатор для обнаружения подозрительного контента в строковых полях.
    Примечание: Это базовый фильтр, он не является полноценной защитой
    от всех видов SQL-инъекций или XSS-атак.
    """
    if not isinstance(value, str):
        return value

    for pattern in COMPILED_DANGEROUS_PATTERNS:
        if pattern.search(value):
            raise ValidationError.from_exception_data(
                title="InputValidationError",
                line_errors=[
                    {
                        "loc": ("malicious_content",),
                        "msg": "Input contains potentially malicious content",
                        "type": "value_error.malicious_content",
                    }
                ],
            )

    return value


def validate_string_length(value: Any, max_length: int = 1000) -> Any:
    """
    Валидатор для ограничения длины строковых полей.
    """
    if isinstance(value, str) and len(value) > max_length:
        raise ValidationError.from_exception_data(
            title="StringLengthError",
            line_errors=[
                {
                    "loc": ("string_too_long",),
                    "msg": f"String too long. Maximum length: {max_length}",
                    "type": "value_error.string_too_long",
                }
            ],
        )

    return value


# Экспорт функций
__all__ = [
    "COMPILED_DANGEROUS_PATTERNS",
    "validate_no_malicious_content",
    "validate_string_length",
]
