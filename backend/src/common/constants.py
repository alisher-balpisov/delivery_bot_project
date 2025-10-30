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


ALL_ROLES_LIST = [UserRole.ADMIN, UserRole.SHOP, UserRole.COURIER]


MIN_TELEGRAM_ID = 1
MAX_TELEGRAM_ID = 2147483647
SECONDS_IN_MINUTE = 60
