"""
Пакет клиентов для взаимодействия с backend API
"""

from .admin_client import AdminClient
from .auth_client import AuthClient
from .client_manager import ClientManager, client_manager
from .disputes_client import DisputesClient
from .notifications_client import NotificationsClient
from .orders_client import OrdersClient
from .system_client import SystemClient
from .users_client import UsersClient

__all__ = [
    "AdminClient",
    "AuthClient",
    "ClientManager",
    "DisputesClient",
    "NotificationsClient",
    "OrdersClient",
    "SystemClient",
    "UsersClient",
    "client_manager",
]
