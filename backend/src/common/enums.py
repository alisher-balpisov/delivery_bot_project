from enum import StrEnum


class TokenType(StrEnum):
    BEARER = "bearer"
    BOT = "bot"


class UserRole(StrEnum):
    ADMIN = "admin"
    SHOP = "shop"
    COURIER = "courier"


class UserStatus(StrEnum):
    PENDING_REGISTRATION = "pending_registration"
    ACTIVE = "active"
    BLOCKED = "blocked"
    INACTIVE = "inactive"


class OrderStatus(StrEnum):
    PENDING = "pending"  # Заказ создан и ожидает назначения свободного курьера
    COURIER_EN_ROUTE = "courier_en_route"  # Курьер назначен и едет за заказом
    DELIVERING = "delivering"  # Курьер доставляет заказ
    SEMI_COMPLETED = "semi_completed"  # Заказ доставлен, но ожидает подтверждения
    COMPLETED = "completed"  # Заказ завершён

    PENDING_COURIER = (
        "pending_courier"  # (только для special_type), заказ ждёт подтверждения курьера
    )
    DISPUTED = "disputed"  # Возник спор
    CANCELED = "canceled"  # Заказ отменён


class OrderType(StrEnum):
    REGULAR = "regular"
    SPECIAL = "special"


class SpecialOrderType(StrEnum):
    TIME = "time"
    DISTANCE = "distance"
    CUSTOM = "custom"
    SUPPLY = "supply"


class DisputeStatus(StrEnum):
    PENDING_REVIEW = "pending_review"  # Спор открыт и ожидает рассмотрения
    IN_REVIEW = "in_review"  # Спор находится в процессе активного рассмотрения
    RESOLVED = "resolved"  # Спор был разрешён


class DisputeResolutionType(StrEnum):
    IN_FAVOR_OF_SHOP = "in_favor_of_shop"  # Спор решён в пользу магазина
    IN_FAVOR_OF_COURIER = "in_favor_of_courier"  # Спор решён в пользу курьера
    COMPROMISE = "compromise"  # Найдено компромиссное решение
    OTHER = "other"  # Другой тип разрешения спора


class ChangeType(StrEnum):
    STATUS_UPDATE = "status_update"
    DETAILS_UPDATE = "details_update"
    COURIER_REASSIGN = "courier_reassign"  # Переназначение курьера на заказ
