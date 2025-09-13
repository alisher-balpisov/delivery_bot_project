"""
Клиент для работы с уведомлениями через backend API
"""

from typing import Any

from .base_client import BaseApiClient


class NotificationsClient(BaseApiClient):
    """Клиент для работы с уведомлениями через backend API."""

    async def send_notification(self, token: str, notification_data: dict) -> dict[str, Any] | None:
        """Отправить уведомление пользователю."""
        return await self._make_request(
            "POST", "/notifications/send", token=token, json_data=notification_data
        )

    async def send_bulk_notifications(
        self, token: str, notifications_data: dict
    ) -> dict[str, Any] | None:
        """Отправить массовые уведомления."""
        return await self._make_request(
            "POST", "/notifications/send-bulk", token=token, json_data=notifications_data
        )

    async def send_order_update_notification(
        self, token: str, order_update_data: dict
    ) -> dict[str, Any] | None:
        """Отправить уведомление об обновлении заказа."""
        return await self._make_request(
            "POST",
            "/notifications/send-order-update",
            token=token,
            json_data=order_update_data,
        )

    async def send_test_notification(self, token: str, test_data: dict) -> dict[str, Any] | None:
        """Отправить тестовое уведомление."""
        return await self._make_request(
            "POST", "/notifications/test-notification", token=token, json_data=test_data
        )
