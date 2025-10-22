# Настройки валидации
from backend.src.common.enums import UserRole

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


ALL_ROLES_LIST = [UserRole.ADMIN, UserRole.SHOP, UserRole.COURIER, UserRole.GUEST, UserRole.PENDING]


MIN_TELEGRAM_ID = 1
MAX_TELEGRAM_ID = 2147483647
MIN_CODE_LENGTH = 1
MAX_CODE_LENGTH = 50
SECONDS_IN_MINUTE = 60
