"""
Исключения для модуля заказов.

Все исключения наследуются от базового AppException для
унифицированной обработки ошибок.
"""

from dataclasses import dataclass

from backend.src.common.exceptions import (
    AccessDeniedException,
    AppException,
    BusinessRuleException,
    ResourceNotFoundException,
    ValidationException,
)

# ==============================================================================
# Исключения заказов
# ==============================================================================


@dataclass
class OrderException(AppException):
    """
    Базовое исключение для всех ошибок, связанных с заказами.

    Все остальные исключения модуля наследуются от него
    для удобной обработки в exception handlers.
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Ошибка при работе с заказом"
        super().__post_init__()


@dataclass
class OrderNotFoundException(ResourceNotFoundException):
    """
    Исключение для случаев, когда заказ не найден в БД.

    Наследуется от ResourceNotFoundException (HTTP 404).

    Args:
        order_id: ID ненайденного заказа
    """

    order_id: int | None = None

    def __post_init__(self) -> None:
        """Формирование сообщения на основе order_id."""
        if not self.detail and self.order_id:
            self.detail = f"Заказ с ID {self.order_id} не найден"
        elif not self.detail:
            self.detail = "Заказ не найден"
        self.resource_type = "Заказ"
        self.resource_id = self.order_id
        super().__post_init__()


@dataclass
class OrderUpdateForbiddenException(AccessDeniedException):
    """
    Исключение для случаев, когда у пользователя нет прав на изменение заказа.

    Может возникать по причинам:
    - Пользователь не владелец заказа (для магазинов/курьеров)
    - Попытка изменить запрещённые поля
    - Попытка изменить заказ в финальном статусе
    - Попытка установить недопустимый статус

    Наследуется от AccessDeniedException (HTTP 403).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "У вас нет прав на изменение этого заказа"
        self.resource_type = "заказ"
        self.action = "изменение"
        super().__post_init__()


@dataclass
class OrderAccessForbiddenException(AccessDeniedException):
    """
    Исключение для случаев, когда у пользователя нет прав на просмотр заказа.

    Может возникать по причинам:
    - Магазин пытается просмотреть чужой заказ
    - Курьер пытается просмотреть не назначенный ему заказ
    - Отсутствует профиль магазина/курьера

    Наследуется от AccessDeniedException (HTTP 403).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "У вас нет прав на доступ к этому заказу"
        self.resource_type = "заказ"
        self.action = "просмотр"
        super().__post_init__()


@dataclass
class OrderInvalidStatusTransitionException(BusinessRuleException):
    """
    Исключение для недопустимых переходов между статусами заказа.

    Например:
    - Попытка завершить заказ, который еще не в доставке
    - Попытка отменить уже завершённый заказ

    Наследуется от BusinessRuleException (HTTP 422).
    """

    current_status: str | None = None
    attempted_status: str | None = None

    def __post_init__(self) -> None:
        """Формирование сообщения на основе статусов."""
        if not self.detail and self.current_status and self.attempted_status:
            self.detail = (
                f"Невозможно изменить статус с '{self.current_status}' на '{self.attempted_status}'"
            )
        elif not self.detail:
            self.detail = "Недопустимый переход между статусами заказа"
        self.rule_name = "status_transition"
        super().__post_init__()


@dataclass
class CourierNotActiveException(ValidationException):
    """
    Исключение для случаев, когда курьер неактивен.

    Возникает при попытке назначить неактивного курьера на заказ.

    Наследуется от ValidationException (HTTP 422).
    """

    courier_id: int | None = None

    def __post_init__(self) -> None:
        """Формирование сообщения на основе courier_id."""
        if not self.detail and self.courier_id:
            self.detail = f"Курьер с ID {self.courier_id} неактивен и не может принимать заказы"
        elif not self.detail:
            self.detail = "Курьер неактивен и не может принимать заказы"
        super().__post_init__()


@dataclass
class OrderValidationException(ValidationException):
    """
    Исключение для ошибок валидации данных заказа.

    Используется для бизнес-правил, не покрытых Pydantic валидацией.

    Наследуется от ValidationException (HTTP 422).
    """

    def __post_init__(self) -> None:
        """Установка сообщения по умолчанию."""
        if not self.detail:
            self.detail = "Ошибка валидации данных заказа"
        super().__post_init__()


# ==============================================================================
# Экспорт
# ==============================================================================

__all__ = [
    "CourierNotActiveException",
    "OrderAccessForbiddenException",
    "OrderException",
    "OrderInvalidStatusTransitionException",
    "OrderNotFoundException",
    "OrderUpdateForbiddenException",
    "OrderValidationException",
]
