"""
Исключения для модуля аутентификации.

Все исключения наследуются от базового AppException для
унифицированной обработки ошибок.
"""

from dataclasses import dataclass, field
from typing import Any

from backend.src.common.exceptions import (
    AppException,
    ConflictException,
    ForbiddenException,
    RateLimitException,
    UnauthorizedException,
)
from fastapi import HTTPException, status

# ==============================================================================
# Исключения аутентификации
# ==============================================================================


@dataclass
class AuthError(AppException):
    """Базовый класс для исключений аутентификации."""

    status_code: int = status.HTTP_400_BAD_REQUEST


@dataclass
class UserAlreadyRegisteredError(ConflictException):
    """
    Выбрасывается, когда пользователь уже зарегистрирован.

    Наследуется от ConflictException (HTTP 409).
    """

    data: dict[str, Any] = field(default_factory=dict)
    access_token: str | None = None

    def __post_init__(self) -> None:
        """Валидация и установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Пользователь уже зарегистрирован"
        super().__post_init__()

    def to_dict(self) -> dict[str, Any]:
        """Сериализация с дополнительными полями."""
        base = super().to_dict()
        base.update(
            {
                "user_data": self.data,
                "access_token": self.access_token,
            }
        )
        return base


@dataclass
class InvalidCredentialsError(UnauthorizedException):
    """
    Неверные учетные данные (например, неверный код).

    Наследуется от UnauthorizedException (HTTP 401).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Неверные учетные данные"
        super().__post_init__()


@dataclass
class AttemptsLimitExceededError(RateLimitException):
    """
    Превышен лимит попыток входа.

    Наследуется от RateLimitException (HTTP 429).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Превышен лимит попыток. Попробуйте позже"
        super().__post_init__()


@dataclass
class AccountLockedError(ForbiddenException):
    """
    Аккаунт временно или постоянно заблокирован.

    Наследуется от ForbiddenException (HTTP 403),
    но использует специфичный статус 423 (Locked).
    """

    status_code: int = status.HTTP_423_LOCKED

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Аккаунт заблокирован"
        super().__post_init__()


@dataclass
class RegistrationIncompleteError(ForbiddenException):
    """
    Пользователь не завершил процесс регистрации.

    Наследуется от ForbiddenException (HTTP 403).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Регистрация не завершена. Завершите процесс регистрации"
        super().__post_init__()


@dataclass
class InvalidRefreshTokenError(UnauthorizedException):
    """
    Refresh token невалиден или истёк.

    Наследуется от UnauthorizedException (HTTP 401).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Refresh token невалиден или истёк"
        super().__post_init__()


@dataclass
class AccountInactiveError(ForbiddenException):
    """
    Аккаунт неактивен.

    Наследуется от ForbiddenException (HTTP 403).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Аккаунт неактивен. Обратитесь к администратору"
        super().__post_init__()


# ==============================================================================
# Предопределённые исключения для совместимости
# ==============================================================================

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось проверить учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
)

ACCOUNT_INACTIVE_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Аккаунт отключен",
)

ACCOUNT_BLOCKED_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Аккаунт заблокирован",
)


# ==============================================================================
# Экспорт
# ==============================================================================

__all__ = [
    "ACCOUNT_BLOCKED_EXCEPTION",
    "ACCOUNT_INACTIVE_EXCEPTION",
    "CREDENTIALS_EXCEPTION",
    "AccountInactiveError",
    "AccountLockedError",
    "AttemptsLimitExceededError",
    "AuthError",
    "InvalidCredentialsError",
    "InvalidRefreshTokenError",
    "RegistrationIncompleteError",
    "UserAlreadyRegisteredError",
]
