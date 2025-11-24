"""
Общие зависимости для FastAPI endpoints.

Этот модуль содержит переиспользуемые зависимости для:
- Пагинации
- Валидации параметров
"""

from typing import Annotated

from backend.src.common.validation import ValidationRules, validate_pagination_params
from fastapi import Depends, Query

# ==============================================================================
# Зависимости пагинации
# ==============================================================================


def get_pagination_params(
    page: Annotated[
        int,
        Query(
            ge=1,
            description="Номер страницы (начиная с 1)",
            example=1,
        ),
    ] = ValidationRules.DEFAULT_PAGE,
    limit: Annotated[
        int,
        Query(
            ge=ValidationRules.MIN_LIMIT,
            le=ValidationRules.MAX_LIMIT,
            description=f"Количество элементов на странице (от {ValidationRules.MIN_LIMIT} до {ValidationRules.MAX_LIMIT})",
            example=ValidationRules.DEFAULT_LIMIT,
        ),
    ] = ValidationRules.DEFAULT_LIMIT,
) -> tuple[int, int]:
    """
    Зависимость для получения параметров пагинации.

    Args:
        page: Номер страницы (начиная с 1)
        limit: Количество элементов на странице

    Returns:
        Кортеж (page, limit) с валидированными значениями

    Raises:
        ValidationException: Если параметры невалидны
    """
    validated_page, validated_limit = validate_pagination_params(page, limit)
    return validated_page, validated_limit


# Type alias для удобства использования
PaginationParams = Annotated[tuple[int, int], Depends(get_pagination_params)]


# ==============================================================================
# Зависимости для фильтрации
# ==============================================================================


# ==============================================================================
# Экспорт
# ==============================================================================

__all__ = [
    "PaginationParams",
    "get_pagination_params",
]
