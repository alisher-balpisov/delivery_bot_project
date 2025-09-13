"""
Менеджер клиентов для взаимодействия с backend API
Централизованное управление всеми клиентами
"""

from .admin_client import AdminClient
from .auth_client import AuthClient
from .disputes_client import DisputesClient
from .notifications_client import NotificationsClient
from .orders_client import OrdersClient
from .system_client import SystemClient
from .users_client import UsersClient


class ClientManager:
    """Менеджер для всех API клиентов"""

    def __init__(self):
        self.auth = AuthClient()
        self.users = UsersClient()
        self.orders = OrdersClient()
        self.notifications = NotificationsClient()
        self.admin = AdminClient()
        self.disputes = DisputesClient()
        self.system = SystemClient()


# Глобальный экземпляр менеджера клиентов
client_manager = ClientManager()
