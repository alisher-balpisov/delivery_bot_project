"""
Централизованная система исключений для backend приложения.

Этот модуль предоставляет базовые классы исключений и утилиты для
унифицированной обработки ошибок во всем приложении.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

from fastapi import HTTPException, status


@dataclass
class AppException(Exception):
    """
    Базовый класс для всех исключений приложения.

    Предоставляет единую структуру для обработки ошибок с поддержкой:
    - HTTP статус кодов
    - Детального описания ошибки
    - Временных меток
    - Дополнительных данных
    - Конвертации в HTTP responses
    """

    detail: str
    status_code: int = status.HTTP_400_BAD_REQUEST
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    extra_data: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Валидация после инициализации."""
        if not self.detail or not self.detail.strip():
            raise ValueError("Поле 'detail' не может быть пустым")
        super().__init__(self.detail)

    def to_dict(self) -> dict[str, Any]:
        """
        Сериализация исключения в словарь.

        Returns:
            Словарь с информацией об ошибке.
        """
        result = {
            "error": self.__class__.__name__,
            "detail": self.detail,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.extra_data:
            result["extra"] = self.extra_data
        return result

    def to_http_exception(self) -> HTTPException:
        """
        Конвертация в HTTPException для FastAPI.

        Returns:
            HTTPException с соответствующими параметрами.
        """
        return HTTPException(status_code=self.status_code, detail=self.detail)


# ==============================================================================
# Mixin классы для различных типов ошибок
# ==============================================================================


class NotFoundMixin:
    """Mixin для ошибок 'не найдено'."""

    status_code: ClassVar[int] = status.HTTP_404_NOT_FOUND


class UnauthorizedMixin:
    """Mixin для ошибок аутентификации."""

    status_code: ClassVar[int] = status.HTTP_401_UNAUTHORIZED


class ForbiddenMixin:
    """Mixin для ошибок доступа."""

    status_code: ClassVar[int] = status.HTTP_403_FORBIDDEN


class ValidationErrorMixin:
    """Mixin для ошибок валидации."""

    status_code: ClassVar[int] = status.HTTP_422_UNPROCESSABLE_ENTITY


class ConflictMixin:
    """Mixin для ошибок конфликта."""

    status_code: ClassVar[int] = status.HTTP_409_CONFLICT


class RateLimitMixin:
    """Mixin для ошибок превышения лимита."""

    status_code: ClassVar[int] = status.HTTP_429_TOO_MANY_REQUESTS


# ==============================================================================
# Общие исключения приложения
# ==============================================================================


@dataclass
class NotFoundException(NotFoundMixin, AppException):
    """Базовый класс для ошибок 'не найдено'."""

    status_code: int = status.HTTP_404_NOT_FOUND


@dataclass
class UnauthorizedException(UnauthorizedMixin, AppException):
    """Базовый класс для ошибок аутентификации."""

    status_code: int = status.HTTP_401_UNAUTHORIZED


@dataclass
class ForbiddenException(ForbiddenMixin, AppException):
    """Базовый класс для ошибок доступа."""

    status_code: int = status.HTTP_403_FORBIDDEN


@dataclass
class ValidationException(ValidationErrorMixin, AppException):
    """Базовый класс для ошибок валидации."""

    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY


@dataclass
class ConflictException(ConflictMixin, AppException):
    """Базовый класс для ошибок конфликта."""

    status_code: int = status.HTTP_409_CONFLICT


@dataclass
class RateLimitException(RateLimitMixin, AppException):
    """Базовый класс для ошибок превышения лимита."""

    status_code: int = status.HTTP_429_TOO_MANY_REQUESTS


# ==============================================================================
# Специализированные исключения
# ==============================================================================


@dataclass
class ResourceNotFoundException(NotFoundException):
    """Ресурс не найден."""

    resource_type: str = field(default="Resource")
    resource_id: int | str | None = None

    def __post_init__(self) -> None:
        """Формирование сообщения на основе ресурса."""
        if not self.detail:
            if self.resource_id:
                self.detail = f"{self.resource_type} с ID {self.resource_id} не найден"
            else:
                self.detail = f"{self.resource_type} не найден"
        super().__post_init__()


@dataclass
class AccessDeniedException(ForbiddenException):
    """Доступ запрещен к ресурсу."""

    resource_type: str | None = None
    action: str | None = None

    def __post_init__(self) -> None:
        """Формирование сообщения на основе контекста."""
        if not self.detail:
            if self.resource_type and self.action:
                self.detail = f"У вас нет прав для {self.action} {self.resource_type}"
            elif self.resource_type:
                self.detail = f"У вас нет прав на доступ к {self.resource_type}"
            else:
                self.detail = "У вас нет прав для выполнения этого действия"
        super().__post_init__()


@dataclass
class BusinessRuleException(ValidationException):
    """Нарушение бизнес-правила."""

    rule_name: str | None = None

    def __post_init__(self) -> None:
        """Формирование сообщения на основе правила."""
        if not self.detail and self.rule_name:
            self.detail = f"Нарушено бизнес-правило: {self.rule_name}"
        super().__post_init__()


# ==============================================================================
# Утилиты
# ==============================================================================


def create_not_found_exception(
    resource_type: str, resource_id: int | str | None = None
) -> ResourceNotFoundException:
    """
    Фабричная функция для создания исключения 'не найдено'.

    Args:
        resource_type: Тип ресурса (например, "Заказ", "Пользователь")
        resource_id: ID ресурса (опционально)

    Returns:
        Настроенное исключение ResourceNotFoundException
    """
    return ResourceNotFoundException(
        detail="", resource_type=resource_type, resource_id=resource_id
    )


def create_access_denied_exception(
    resource_type: str | None = None, action: str | None = None
) -> AccessDeniedException:
    """
    Фабричная функция для создания исключения доступа.

    Args:
        resource_type: Тип ресурса (опционально)
        action: Действие (опционально)

    Returns:
        Настроенное исключение AccessDeniedException
    """
    return AccessDeniedException(detail="", resource_type=resource_type, action=action)


__all__ = [
    "AccessDeniedException",
    "AppException",
    "BusinessRuleException",
    "ConflictException",
    "ForbiddenException",
    "NotFoundException",
    "RateLimitException",
    "ResourceNotFoundException",
    "UnauthorizedException",
    "ValidationException",
    "create_access_denied_exception",
    "create_not_found_exception",
]
