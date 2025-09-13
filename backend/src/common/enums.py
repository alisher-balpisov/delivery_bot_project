from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"  # Администратор системы
    SHOP = "shop"  # Магазин
    COURIER = "courier"  # Курьер

    GUEST = "guest"
    PENDING = "pending"  # Временная роль для незарегистрированных пользователей


class OrderStatus(str, Enum):
    CREATED = "created"  # В ожидании (не назначен курьеру)
    ACCEPTED = "accepted"  # Курьер принял заказ
    PICKING_UP = "picking_up"  # В пути за заказом (курьер заберает заказ)
    IN_PROGRESS = "in_progress"  # В пути к получателю (забрал, едет к получателю)
    DELIVERED = "delivered"  # Завершен (курьер завершил доставку)
    COMPLETED = "completed"  # Подтвержден магазином или автоматически через 12 часов
    CANCELLED = "cancelled"  # Отменен
    DISPUTED = "disputed"  # Спор


class OrderType(str, Enum):
    normal = "normal"  # обычный: курьер не видит цену, фиксированная 3000, зависит от зоны
    special = "special"  # особенный: курьер видит цену заказа
    rush_hour = "rush_hour"  # заказ ко времени доставки вне периода 9:00-21:00 (+1000-1500)
    long_distance = "long_distance"  # заказ на большое расстояние (вне зоны)
    important = "important"  # особый заказ (большой, дорогой, особому клиенту)


class DisputeStatus(str, Enum):
    OPEN = "open"  # Открыт
    IN_REVIEW = "in_review"  # На рассмотрении
    RESOLVED = "resolved"  # Решено
    CLOSED = "closed"  # Закрыто


class TokenType(str, Enum):
    BEARER = "Bearer"
    BOT = "Bot"
