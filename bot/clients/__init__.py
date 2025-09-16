from bot.clients.base_client import ConnectionPool

from .admin_client import AdminClient
from .auth_client import AuthClient
from .disputes_client import DisputesClient
from .notifications_client import NotificationsClient
from .orders_client import OrdersClient
from .system_client import SystemClient
from .users_client import UsersClient


class ClientManager:
    """Менеджер для всех API клиентов"""

    def __init__(self, pool: ConnectionPool):
        self.auth = AuthClient(pool=pool)
        self.users = UsersClient(pool=pool)
        self.orders = OrdersClient(pool=pool)
        self.notifications = NotificationsClient(pool=pool)
        self.admin = AdminClient(pool=pool)
        self.disputes = DisputesClient(pool=pool)
        self.system = SystemClient(pool=pool)


__all__ = [
    "AdminClient",
    "AuthClient",
    "ClientManager",
    "DisputesClient",
    "NotificationsClient",
    "OrdersClient",
    "SystemClient",
    "UsersClient",
]
