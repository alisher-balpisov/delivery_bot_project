"""
Пакет сообщений бота.

Реэкспортирует классы сообщений для обратной совместимости.
"""

from .admin import AdminKeyboard, AdminMessages, AdminService
from .auth import AuthMessages, AuthService
from .common import (
    CommonMessages,
    CommonServiceMessages,
    CourierMessages,
    DisputeMessages,
    PublicMessages,
    ShopMessages,
)
from .errors import BaseClientMessages, ErrorMessages
from .orders import OrderMessages

# Aliases for backward compatibility
AdminServiceMessages = AdminService
AdminKeyboardMessages = AdminKeyboard
AuthServiceMessages = AuthService
BotMessages = CommonMessages

__all__ = [
    "AdminKeyboardMessages",
    "AdminMessages",
    "AdminServiceMessages",
    "AuthMessages",
    "AuthServiceMessages",
    "BaseClientMessages",
    "BotMessages",
    "CommonMessages",
    "CommonServiceMessages",
    "CourierMessages",
    "DisputeMessages",
    "ErrorMessages",
    "OrderMessages",
    "PublicMessages",
    "ShopMessages",
]
