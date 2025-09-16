from .base_client import BaseApiClient, RequestResult


class OrdersClient(BaseApiClient):
    """Клиент для работы с заказами через backend API."""

    async def create_order(self, telegram_id: int, order_data: dict) -> RequestResult:
        """Создать новый заказ."""
        return await self._make_request(
            "POST",
            "/orders/",
            telegram_id=telegram_id,
            json_data=order_data,
            expected_status=201,
        )

    async def get_order_details(self, telegram_id: int, order_id: int) -> RequestResult:
        """Получить детали заказа по ID."""
        return await self._make_request("GET", f"/orders/{order_id}", telegram_id=telegram_id)

    async def get_user_orders(self, telegram_id: int) -> RequestResult:
        """Получить заказы пользователя (в зависимости от роли)."""
        return await self._make_request("GET", "/orders/my", telegram_id=telegram_id)

    async def update_order_status(
        self, telegram_id: int, order_id: int, status_data: dict
    ) -> RequestResult:
        """Обновить статус заказа."""
        return await self._make_request(
            "PATCH", f"/orders/{order_id}", telegram_id=telegram_id, json_data=status_data
        )

    async def get_available_orders(self, telegram_id: int) -> RequestResult:
        """Получить доступные заказы (для курьеров)."""
        return await self._make_request("GET", "/orders/available", telegram_id=telegram_id)
