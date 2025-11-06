from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status


@dataclass
class AuthError(Exception):
    """Базовый класс для исключений аутентификации."""

    detail: str
    status_code: int = 400
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Валидация после инициализации."""
        if not self.detail or not self.detail.strip():
            raise ValueError("Поле 'detail' не может быть пустым")
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

    data: dict[str, Any] = field(default_factory=dict[str, Any])
    access_token: str | None = None

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
