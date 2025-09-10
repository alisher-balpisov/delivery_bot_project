"""
Менеджер клиентов для взаимодействия с backend API
Централизованное управление всеми клиентами
"""

from bot.admin_client import AdminClient
from bot.auth_client import AuthClient
from bot.disputes_client import DisputesClient
from bot.notifications_client import NotificationsClient
from bot.orders_client import OrdersClient
from bot.system_client import SystemClient
from bot.users_client import UsersClient


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
