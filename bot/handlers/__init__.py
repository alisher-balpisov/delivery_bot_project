"""
Пакет обработчиков команд и сообщений Telegram бота
"""

from .auth import auth_router
from .auth import protected_router as protected_auth_router
from .base_handlers import protected_router as protected_base_handlers_router
from .base_handlers import public_router
from .orders_handlers import orders_router

__all__ = [
    "auth_router",
    "orders_router",
    "protected_auth_router",
    "protected_base_handlers_router",
    "public_router",
]
