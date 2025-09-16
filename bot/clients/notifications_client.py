from .base_client import BaseApiClient, RequestResult


class NotificationsClient(BaseApiClient):
    """Клиент для работы с уведомлениями через backend API."""

    async def send_notification(self, telegram_id: int, notification_data: dict) -> RequestResult:
        """Отправить уведомление пользователю."""
        notification_data["telegram_id"] = telegram_id
        return await self._make_request("POST", "/notifications/send", json_data=notification_data)

    async def send_bulk_notifications(
        self, telegram_id: int, notifications_data: dict
    ) -> RequestResult:
        """Отправить массовые уведомления."""
        notifications_data["telegram_id"] = telegram_id
        return await self._make_request(
            "POST", "/notifications/send-bulk", json_data=notifications_data
        )

    async def send_order_update_notification(
        self, telegram_id: int, order_update_data: dict
    ) -> RequestResult:
        """Отправить уведомление об обновлении заказа."""
        order_update_data["telegram_id"] = telegram_id
        return await self._make_request(
            "POST",
            "/notifications/send-order-update",
            telegram_id=telegram_id,
            json_data=order_update_data,
        )

    async def send_test_notification(self, telegram_id: int, test_data: dict) -> RequestResult:
        """Отправить тестовое уведомление."""
        test_data["telegram_id"] = telegram_id
        return await self._make_request(
            "POST", "/notifications/test-notification", json_data=test_data
        )
