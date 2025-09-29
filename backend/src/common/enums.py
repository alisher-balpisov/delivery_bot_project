from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    SHOP = "SHOP"
    COURIER = "COURIER"
    GUEST = "GUEST"
    PENDING = "PENDING"


class OrderStatus(str, Enum):
    CREATED = "CREATED"  # В ожидании (не назначен курьеру)
    ACCEPTED = "ACCEPTED"  # Курьер принял заказ
    PICKING_UP = "PICKING_UP"  # В пути за заказом (курьер забирает заказ)
    IN_PROGRESS = "IN_PROGRESS"  # В пути к получателю (забрал, едет к получателю)
    DELIVERED = "DELIVERED"  # Завершен (курьер завершил доставку)
    COMPLETED = "COMPLETED"  # Подтвержден магазином или автоматически через 12 часов
    CANCELLED = "CANCELLED"  # Отменен
    DISPUTED = "DISPUTED"  # Спор


class OrderType(str, Enum):
    NORMAL = "NORMAL"  # обычный: курьер не видит цену, фиксированная 3000, зависит от зоны
    SPECIAL = "SPECIAL"  # особенный: курьер видит цену заказа
    RUSH_HOUR = "RUSH_HOUR"  # заказ ко времени доставки вне периода 9:00-21:00 (+1000-1500)
    LONG_DISTANCE = "LONG_DISTANCE"  # заказ на большое расстояние (вне зоны)
    IMPORTANT = "IMPORTANT"  # особый заказ (большой, дорогой, особому клиенту)


class DisputeStatus(str, Enum):
    OPEN = "OPEN"  # Открыт
    IN_REVIEW = "IN_REVIEW"  # На рассмотрении
    RESOLVED = "RESOLVED"  # Решено
    CLOSED = "CLOSED"  # Закрыто


class TokenType(str, Enum):
    BEARER = "BEARER"
    BOT = "BOT"
