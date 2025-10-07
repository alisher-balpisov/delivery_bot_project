from enum import Enum, StrEnum


class TokenType(str, Enum):
    BEARER = "BEARER"
    BOT = "BOT"







class UserRole(str, Enum):
    ADMIN = "ADMIN"
    SHOP = "SHOP"
    COURIER = "COURIER"


class UserStatus(str, Enum):
    pending_registration = "pending_registration"
    active = "active"
    blocked = "blocked"
    inactive = "inactive"


class OrderStatus(str, Enum):
    pending = "pending"  # В ожидании свободного курьера
    courier_en_route = "courier_en_route"  # Курьер едет за заказом
    delivering = "delivering"  # Курьер доставляет заказ
    semi_completed = "semi_completed"  # Завершён, ожидает подтверждения
    completed = "completed"  # Завершён и подтверждён
    disputed = "disputed"  # В споре
    canceled = "canceled"  # Отменён


class OrderType(str, Enum):
    regular = "regular"
    special = "special"


class SpecialOrderType(str, Enum):
    time = "time"
    distance = "distance"
    custom = "custom"
    supply = "supply"


class DisputeStatus(str, Enum):
    pending_review = "pending_review"
    in_review = "in_review"
    resolved = "resolved"


class DisputeResolutionType(str, Enum):
    in_favor_of_shop = "in_favor_of_shop"
    in_favor_of_courier = "in_favor_of_courier"
    compromise = "compromise"
    other = "other"


class ChangeType(str, Enum):
    status_update = "status_update"
    details_update = "details_update"
    courier_reassign = "courier_reassign"
