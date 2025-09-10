from enum import Enum


class UserRole(str, Enum):
    """Роли пользователей в системе."""

    ADMIN = "admin"
    SHOP = "shop"
    COURIER = "courier"
    GUEST = "guest"


class OrderStatus(str, Enum):
    """Статусы заказов."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    PICKED_UP = "picked_up"
    IN_DELIVERY = "in_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class DisputeStatus(str, Enum):
    """Статусы споров."""

    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


# Эмодзи для ролей
ROLE_EMOJIS: dict[str, str] = {
    UserRole.ADMIN: "👑",
    UserRole.SHOP: "🏪",
    UserRole.COURIER: "🏍️",
    UserRole.GUEST: "👤",
}

# Команды по ролям
ROLE_COMMANDS: dict[str, dict[str, any]] = {
    UserRole.ADMIN: {
        "icon": "👑",
        "title": "Администратор:",
        "commands": [
            "/admin - управление системой\n",
            "/stats - полная статистика\n",
            "/disputes - управление спорами\n",
            "/broadcast - массовая рассылка",
        ],
    },
    UserRole.SHOP: {
        "icon": "🏪",
        "title": "Магазин:",
        "commands": [
            "/new_order - создать заказ\n",
            "/my_orders - мои заказы\n",
            "/order_history - история заказов\n",
            "/dispute - открыть спор",
        ],
    },
    UserRole.COURIER: {
        "icon": "🏍️",
        "title": "Курьер:",
        "commands": [
            "/available_orders - доступные заказы\n",
            "/my_orders - активные доставки\n",
            "/earnings - мои заработки\n",
            "/rating - мой рейтинг",
        ],
    },
}

# Лимиты и ограничения
RATE_LIMITS = {
    UserRole.ADMIN: 100,  # запросов в минуту
    UserRole.SHOP: 30,
    UserRole.COURIER: 30,
    UserRole.GUEST: 10,
}

CACHE_TTL = {
    "token_validation": 300,  # 5 минут
    "user_profile": 600,  # 10 минут
    "order_list": 60,  # 1 минута
    "statistics": 1800,  # 30 минут
}

# Сообщения об ошибках
ERROR_MESSAGES = {
    "unauthorized": "❌ Сначала авторизуйтесь с помощью /start",
    "forbidden": "❌ У вас нет прав для выполнения этого действия",
    "not_found": "❌ Запрошенный ресурс не найден",
    "server_error": "❌ Произошла ошибка сервера. Попробуйте позже",
    "network_error": "❌ Ошибка соединения. Проверьте подключение к интернету",
    "invalid_input": "❌ Некорректные данные. Проверьте ввод и попробуйте снова",
}

# Настройки валидации
VALIDATION = {
    "min_order_price": 100,  # минимальная цена заказа в тенге
    "max_order_price": 1000000,  # максимальная цена заказа
    "max_description_length": 500,
    "max_address_length": 200,
    "dispute_time_limit": 86400,  # 24 часа для открытия спора
}

# Комиссии и платежи
COMMISSION = {
    "platform_fee_percent": 10,  # комиссия платформы в процентах
    "min_commission": 50,  # минимальная комиссия в тенге
    "payment_methods": ["cash", "card", "kaspi"],
}
