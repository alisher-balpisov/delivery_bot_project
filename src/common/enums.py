from enum import Enum


class UserRole(Enum):
    admin = "admin"  # Администратор системы
    shop = "shop"  # Магазин
    courier = "courier"  # Курьер


class OrderStatus(Enum):
    created = "created"  # В ожидании (не назначен курьеру)
    accepted = "accepted"  # Курьер принял заказ
    picking_up = "picking_up"  # В пути за заказом (курьер заберает заказ)
    in_progress = "in_progress"  # В пути к получателю (забрал, едет к получателю)
    delivered = "delivered"  # Завершен (курьер завершил доставку)
    completed = "completed"  # Подтвержден магазином или автоматически через 12 часов
    cancelled = "cancelled"  # Отменен
    disputed = "disputed"  # Спор


class OrderType(Enum):
    normal = "normal"  # обычный: курьер не видит цену, фиксированная 3000, зависит от зоны
    special = "special"  # особенный: курьер видит цену заказа
    rush_hour = "rush_hour"  # заказ ко времени доставки вне периода 9:00-21:00 (+1000-1500)
    long_distance = "long_distance"  # заказ на большое расстояние (вне зоны)
    important = "important"  # особый заказ (большой, дорогой, особому клиенту)


class DisputeStatus(Enum):
    open = "open"  # Открыт
    in_review = "in_review"  # На рассмотрении
    resolved = "resolved"  # Решено
    closed = "closed"  # Закрыто
