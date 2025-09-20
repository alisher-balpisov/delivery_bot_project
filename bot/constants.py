from enum import Enum

from backend.src.common.enums import UserRole

MAX_REGISTRATION_ATTEMPTS = 5
STATS_TIMEOUT = 10  # секунды
MAX_MESSAGE_LENGTH = 4000  # максимум Telegram
MAX_CODES_DISPLAY = 10

ROLE_EMOJI_MAP = {
    UserRole.ADMIN: "👑",
    UserRole.SHOP: "🏪",
    UserRole.COURIER: "🏍️",
    UserRole.GUEST: "👤",
    UserRole.PENDING: "👤",
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
