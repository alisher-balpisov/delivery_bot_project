"""
Result type для типобезопасной обработки ошибок.

Использует Pydantic для валидации и сериализации.
Альтернатива exceptions для flow control.

Usage:
    >>> from bot.utils.result import Result, Success, Failure
    >>>
    >>> async def get_user(user_id: int) -> Result[User]:
    >>>     try:
    >>>         user = await repository.get(user_id)
    >>>         return Success(data=user)
    >>>     except NotFoundError:
    >>>         return Failure(error="Пользователь не найден")
    >>>
    >>> # Pattern matching
    >>> result = await get_user(123)
    >>> match result:
    >>>     case Success(data=user):
    >>>         print(f"Found: {user.name}")
    >>>     case Failure(error=msg):
    >>>         print(f"Error: {msg}")
"""

from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Success[T](BaseModel):
    """
    Успешный результат операции.

    Attributes:
        data: Данные результата

    Examples:
        >>> user = User(id=1, name="Alice")
        >>> result = Success(data=user)
        >>> result.data.name
        'Alice'
    """

    data: T = Field(description="Данные успешного результата")

    def __bool__(self) -> bool:
        """Success всегда True для if-проверок."""
        return True


class Failure(BaseModel):
    """
    Ошибка выполнения операции.

    Attributes:
        error: Сообщение об ошибке
        details: Дополнительные детали (опционально)

    Examples:
        >>> result = Failure(error="Пользователь не найден", details={"user_id": 123})
        >>> result.error
        'Пользователь не найден'
    """

    error: str = Field(min_length=1, description="Сообщение об ошибке")
    details: dict | None = Field(default=None, description="Дополнительная информация")

    def __bool__(self) -> bool:
        """Failure всегда False для if-проверок."""
        return False


# Type alias для удобства
type Result[T] = Success[T] | Failure


def is_success[T](result: Result[T]) -> bool:
    """
    Проверяет, является ли результат успешным.

    Args:
        result: Результат для проверки

    Returns:
        True если Success, False если Failure

    Examples:
        >>> result = Success(data=42)
        >>> is_success(result)
        True
    """
    return isinstance(result, Success)


def is_failure[T](result: Result[T]) -> bool:
    """
    Проверяет, является ли результат ошибкой.

    Args:
        result: Результат для проверки

    Returns:
        True если Failure, False если Success

    Examples:
        >>> result = Failure(error="Ошибка")
        >>> is_failure(result)
        True
    """
    return isinstance(result, Failure)


def unwrap[T](result: Result[T]) -> T:
    """
    Извлекает данные из Success или выбрасывает исключение для Failure.

    Args:
        result: Результат для извлечения

    Returns:
        Данные из Success

    Raises:
        ValueError: Если result - это Failure

    Examples:
        >>> result = Success(data=42)
        >>> unwrap(result)
        42

        >>> result = Failure(error="Ошибка")
        >>> unwrap(result)
        ValueError: Ошибка
    """
    if isinstance(result, Success):
        return result.data
    raise ValueError(result.error)


def unwrap_or(result: Result[T], default: T) -> T:
    """
    Извлекает данные из Success или возвращает default для Failure.

    Args:
        result: Результат для извлечения
        default: Значение по умолчанию

    Returns:
        Данные из Success или default

    Examples:
        >>> result = Success(data=42)
        >>> unwrap_or(result, 0)
        42

        >>> result = Failure(error="Ошибка")
        >>> unwrap_or(result, 0)
        0
    """
    if isinstance(result, Success):
        return result.data
    return default
