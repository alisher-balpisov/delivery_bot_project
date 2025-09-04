"""
Кастомные валидаторы для Pydantic схем.
Обеспечивают дополнительную защиту от SQL injection и XSS атак.
"""

import re
from typing import Any

# Список подозрительных паттернов
DANGEROUS_PATTERNS = [
    r";\s*--",  # SQL комментарии
    r";\s*/\*",  # Начало SQL блока комментариев
    r"union\s+select",  # UNION SELECT атаки
    r"<\s*script",  # XSS script tags
    r"javascript\s*:",  # JavaScript URI
    r"on\w+\s*=",  # XSS event handlers
    r"<iframe",  # XSS iframe
    r"eval\s*\(",  # JavaScript eval
]


def validate_no_malicious_content(value: Any) -> Any:
    """
    Валидатор для обнаружения подозрительного контента в строковых полях.
    """
    if not isinstance(value, str):
        return value

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            from pydantic import ValidationError

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
        from pydantic import ValidationError

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
    "DANGEROUS_PATTERNS",
    "validate_no_malicious_content",
    "validate_string_length",
]
