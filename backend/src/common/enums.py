# common/enums.py
from enum import Enum


class UserRole(Enum):
    admin = "admin"
    shop = "shop"
    courier = "courier"


class OrderStatus(Enum):
    created = "created"
    accepted = "accepted"
    in_progress = "in_progress"
    delivered = "delivered"
    completed = "completed"
    cancelled = "cancelled"
    disputed = "disputed"


class OrderType(Enum):
    normal = "normal"
    urgent = "urgent"
    scheduled = "scheduled"


class DisputeStatus(Enum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    closed = "closed"
