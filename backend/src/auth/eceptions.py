"""Модуль исключений аутентификации."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AuthError(Exception):
    """Базовый класс для исключений аутентификации."""

    detail: str
    status_code: int = 400
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Валидация после инициализации."""
        if not self.detail or not self.detail.strip():
            raise ValueError("Detail cannot be empty")
        super().__init__(self.detail)

    def to_dict(self) -> dict[str, Any]:
        """Сериализация исключения в словарь."""
        return {
            "error": self.__class__.__name__,
            "detail": self.detail,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class UserAlreadyRegisteredError(AuthError):
    """Выбрасывается, когда пользователь уже зарегистрирован."""

    user_data: dict[str, Any] = field(default_factory=dict)
    access_token: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Сериализация с дополнительными полями."""
        base = super().to_dict()
        base.update(
            {
                "user_data": self.user_data,
                "access_token": self.access_token,
            }
        )
        return base


@dataclass
class InvalidCredentialsError(AuthError):
    """Неверные учетные данные (например, неверный код)."""

    status_code: int = 401


@dataclass
class AttemptsLimitExceededError(AuthError):
    """Превышен лимит попыток входа."""

    status_code: int = 429


@dataclass
class AccountLockedError(AuthError):
    """Аккаунт временно или постоянно заблокирован."""

    status_code: int = 423
