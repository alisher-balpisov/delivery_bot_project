from enum import Enum, StrEnum

from pydantic import BaseModel, ConfigDict

BOT_NAME = "Delivery Bot"
MAX_REGISTRATION_ATTEMPTS = 5
STATS_TIMEOUT = 10  # секунды
MAX_MESSAGE_LENGTH = 4000  # максимум Telegram
MAX_CODES_DISPLAY = 10


class DisputeStatus(StrEnum):
    PENDING_REVIEW = "pending_review"  # Спор открыт и ожидает рассмотрения
    IN_REVIEW = "in_review"  # Спор находится в процессе активного рассмотрения
    RESOLVED = "resolved"  # Спор был разрешён


class UserStatus(StrEnum):
    PENDING_REGISTRATION = "pending_registration"
    ACTIVE = "active"
    BLOCKED = "blocked"
    INACTIVE = "inactive"


class CourierListItem(BaseModel):
    """Схема элемента списка курьеров."""

    id: int
    full_name: str
    is_active: bool  # Статус смены (on shift)
    user_status: UserStatus  # Статус пользователя (active/inactive/blocked)

    model_config = ConfigDict(from_attributes=True)


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


class ShopListItem(BaseModel):
    id: int
    name: str | None
    status: UserStatus
    telegram_id: int


class UserRole(StrEnum):
    GUEST = "guest"
    ADMIN = "admin"
    SHOP = "shop"
    COURIER = "courier"


ROLE_EMOJI_MAP = {
    UserRole.ADMIN: "👑",
    UserRole.SHOP: "🏪",
    UserRole.COURIER: "🏍️",
    UserRole.GUEST: "👤",
}

STATS_EMOJIS = {
    "users": "👥",
    "orders": "📦",
    "active_orders": "🚀",
    "completed_orders": "✅",
    "cancelled_orders": "❌",
    "disputes": "⚠️",
    "unresolved_disputes": "🟡",
}


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


error_map = {
    400: "Неверные данные",
    401: "Ошибка авторизации",
    403: "Недостаточно прав",
    404: "Ресурс не найден",
}


ROLE_COMMANDS: dict[str, dict[str, any]] = {
    UserRole.GUEST: {
        "icon": ROLE_EMOJI_MAP[UserRole.GUEST],
        "title": "Гость:",
        "commands": [
            "/start - авторизация\n",
            "/register - регистрация",
        ],
    },
    UserRole.ADMIN: {
        "icon": ROLE_EMOJI_MAP[UserRole.ADMIN],
        "title": "Администратор:",
        "commands": [
            "/admin - Панель администратора\n",
            "/system_stats - Системная статистика\n",
            "/broadcast - Массовая рассылка\n",
            "/test_api - Тест соединения с API",
        ],
    },
    UserRole.SHOP: {
        "icon": ROLE_EMOJI_MAP[UserRole.SHOP],
        "title": "Магазин:",
        "commands": [
            "/new_order - создать заказ\n",
            "/my_orders - мои заказы\n",
            "/order_history - история заказов\n",
            "/dispute - открыть спор",
        ],
    },
    UserRole.COURIER: {
        "icon": ROLE_EMOJI_MAP[UserRole.COURIER],
        "title": "Курьер:",
        "commands": [
            "/available_orders - доступные заказы\n",
            "/my_orders - активные доставки\n",
            "/earnings - мои заработки\n",
            "/rating - мой рейтинг",
        ],
    },
}
