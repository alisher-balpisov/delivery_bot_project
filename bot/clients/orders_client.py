from .base_client import BaseApiClient, RequestResult


class OrdersClient(BaseApiClient):
    """Клиент для работы с заказами через backend API."""

    async def create_order(self, token: str, order_data: dict) -> RequestResult:
        """Создать новый заказ."""
        return await self._make_request(
            "POST",
            "/orders/",
            token=token,
            json_data=order_data,
            expected_status=201,
        )

    async def get_order_details(self, token: str, order_id: int) -> RequestResult:
        """Получить детали заказа по ID."""
        return await self._make_request("GET", f"/orders/{order_id}", token=token)

    async def get_user_orders(self, token: str) -> RequestResult:
        """Получить заказы пользователя (в зависимости от роли)."""
        return await self._make_request("GET", "/orders/my", token=token)

    async def update_order_status(
        self, token: str, order_id: int, status_data: dict
    ) -> RequestResult:
        """Обновить статус заказа."""
        return await self._make_request(
            "PATCH", f"/orders/{order_id}", token=token, json_data=status_data
        )

    async def get_available_orders(self, token: str) -> RequestResult:
        """Получить доступные заказы (для курьеров)."""
        return await self._make_request("GET", "/orders/available", token=token)
