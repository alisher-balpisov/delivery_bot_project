"""
Исключения для модуля споров.

Все исключения наследуются от базового AppException для
унифицированной обработки ошибок.
"""

from dataclasses import dataclass

from backend.src.common.exceptions import AccessDeniedException, AppException

# ==============================================================================
# Исключения споров
# ==============================================================================


@dataclass
class DisputeError(AppException):
    """Базовый класс для ошибок, связанных со спорами."""

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Ошибка при работе со спором"
        super().__post_init__()


@dataclass
class DisputeAccessDenied(AccessDeniedException):
    """
    Выбрасывается, когда пользователь пытается получить доступ к спору без разрешения.

    Наследуется от AccessDeniedException (HTTP 403).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "У вас нет прав на доступ к этому спору"
        super().__post_init__()


@dataclass
class DisputeActionError(DisputeError):
    """
    Выбрасывается при недопустимых действиях со спором.

    Примеры:
    - Создание дубликата спора
    - Изменение закрытого спора
    - Разрешение спора без необходимых прав
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Недопустимое действие со спором"
        super().__post_init__()


# ==============================================================================
# Экспорт
# ==============================================================================

__all__ = [
    "DisputeAccessDenied",
    "DisputeActionError",
    "DisputeError",
]
