from enum import StrEnum, auto


class TokenType(StrEnum):
    BEARER = auto()
    ACCESS = auto()
    REFRESH = auto()
    BOT = auto()


class UserRole(StrEnum):
    GUEST = auto()
    ADMIN = auto()
    SHOP = auto()
    COURIER = auto()


class UserStatus(StrEnum):
    PENDING_REGISTRATION = auto()
    ACTIVE = auto()
    BLOCKED = auto()
    INACTIVE = auto()


class DeliveryTimeType(StrEnum):
    """Тип времени доставки заказа."""

    ASAP = auto()  # Срочная доставка (как можно быстрее)
    TODAY = auto()  # В течение дня (по умолчанию)
    SCHEDULED = auto()  # К конкретному времени (delivery_time)


class OrderStatus(StrEnum):
    """Статусы заказа согласно DBML-схеме."""

    PENDING = auto()  # Заказ создан и ожидает назначения курьера
    PENDING_COURIER = auto()  # Ожидает подтверждения курьера
    COURIER_EN_ROUTE = auto()  # Курьер назначен и едет за заказом
    DELIVERING = auto()  # Курьер доставляет заказ
    AWAITING_CONFIRMATION = auto()  # Доставлен, ожидает подтверждения
    COMPLETED = auto()  # Заказ завершён
    DISPUTED = auto()  # Возник спор
    CANCELED = auto()  # Заказ отменён

    @classmethod
    def active_statuses(cls) -> set[str]:
        """Возвращает множество активных статусов заказа."""
        return {
            cls.PENDING.value,
            cls.PENDING_COURIER.value,
            cls.COURIER_EN_ROUTE.value,
            cls.DELIVERING.value,
            cls.AWAITING_CONFIRMATION.value,
            cls.DISPUTED.value,
        }

    @classmethod
    def completed_statuses(cls) -> set[str]:
        """Возвращает множество завершённых статусов заказа."""
        return {
            cls.COMPLETED.value,
            cls.CANCELED.value,
        }


class OrderType(StrEnum):
    REGULAR = auto()
    TIME = auto()
    DISTANCE = auto()
    CUSTOM = auto()
    SUPPLY = auto()


class DisputeStatus(StrEnum):
    CANCELLED = auto()  # Спор отменен
    PENDING_REVIEW = auto()  # Спор открыт и ожидает рассмотрения
    IN_REVIEW = auto()  # Спор находится в процессе активного рассмотрения
    RESOLVED = auto()  # Спор был разрешён


class DisputeResolutionType(StrEnum):
    IN_FAVOR_OF_SHOP = auto()  # Спор решён в пользу магазина
    IN_FAVOR_OF_COURIER = auto()  # Спор решён в пользу курьера
    COMPROMISE = auto()  # Найдено компромиссное решение
    OTHER = auto()  # Другой тип разрешения спора


class ChangeType(StrEnum):
    STATUS_UPDATE = auto()
    DETAILS_UPDATE = auto()
    COURIER_REASSIGN = auto()  # Переназначение курьера на заказ
