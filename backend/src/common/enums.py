from enum import StrEnum


class TokenType(StrEnum):
    BEARER = "bearer"
    ACCESS = "access"
    REFRESH = "refresh"
    BOT = "bot"


class UserRole(StrEnum):
    GUEST = "GUEST"
    ADMIN = "ADMIN"
    SHOP = "SHOP"
    COURIER = "COURIER"


class UserStatus(StrEnum):
    PENDING_REGISTRATION = "PENDING_REGISTRATION"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    INACTIVE = "INACTIVE"


class DeliveryTimeType(StrEnum):
    """Тип времени доставки заказа."""

    ASAP = "ASAP"  # Срочная доставка (как можно быстрее)
    TODAY = "TODAY"  # В течение дня (по умолчанию)
    SCHEDULED = "SCHEDULED"  # К конкретному времени (delivery_time)


class OrderStatus(StrEnum):
    """Статусы заказа согласно DBML-схеме."""

    # ВАЖНО: Значения должны соответствовать тем, что в базе данных (часто в верхнем регистре)
    PENDING = "PENDING"  # Заказ создан и ожидает назначения курьера
    PENDING_COURIER = "PENDING_COURIER"  # Ожидает подтверждения курьера (special orders)
    COURIER_EN_ROUTE = "COURIER_EN_ROUTE"  # Курьер назначен и едет за заказом
    DELIVERING = "DELIVERING"  # Курьер доставляет заказ
    AWAITING_CONFIRMATION = (
        "SEMI_COMPLETED"  # Доставлен, ожидает подтверждения (в БД SEMI_COMPLETED)
    )
    COMPLETED = "COMPLETED"  # Заказ завершён
    DISPUTED = "DISPUTED"  # Возник спор
    CANCELED = "CANCELED"  # Заказ отменён

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
    REGULAR = "REGULAR"
    SPECIAL = "SPECIAL"


class SpecialOrderType(StrEnum):
    TIME = "TIME"
    DISTANCE = "DISTANCE"
    CUSTOM = "CUSTOM"
    SUPPLY = "SUPPLY"


class DisputeStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"  # Спор открыт и ожидает рассмотрения
    IN_REVIEW = "IN_REVIEW"  # Спор находится в процессе активного рассмотрения
    RESOLVED = "RESOLVED"  # Спор был разрешён


class DisputeResolutionType(StrEnum):
    IN_FAVOR_OF_SHOP = "IN_FAVOR_OF_SHOP"  # Спор решён в пользу магазина
    IN_FAVOR_OF_COURIER = "IN_FAVOR_OF_COURIER"  # Спор решён в пользу курьера
    COMPROMISE = "COMPROMISE"  # Найдено компромиссное решение
    OTHER = "OTHER"  # Другой тип разрешения спора


class ChangeType(StrEnum):
    STATUS_UPDATE = "STATUS_UPDATE"
    DETAILS_UPDATE = "DETAILS_UPDATE"
    COURIER_REASSIGN = "COURIER_REASSIGN"  # Переназначение курьера на заказ
