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

    async def update_order(self, token: str, order_id: int, data: dict) -> RequestResult:
        """Обновить данные заказа (статус, цена и т.д.)."""
        return await self._make_request(
            "PATCH",
            f"/orders/{order_id}",
            token=token,
            json_data=data,
            custom_headers={"Content-Type": "application/json"},
        )

    async def add_order_note(self, token: str, order_id: int, content: str) -> RequestResult:
        """Добавить заметку к заказу."""
        return await self._make_request(
            "POST",
            f"/orders/{order_id}/notes",
            token=token,
            json_data={"content": content},
            custom_headers={"Content-Type": "application/json"},
            expected_status=201,
        )

    async def get_available_orders(self, token: str) -> RequestResult:
        """Получить доступные заказы (для курьеров)."""
        return await self._make_request("GET", "/orders/available", token=token)

    async def get_orders_history(
        self,
        token: str,
        page: int = 1,
        limit: int = 10,
        status: str | None = None,
        shop_id: int | None = None,
        courier_id: int | None = None,
        current: bool | None = None,
    ) -> RequestResult:
        """Получить историю заказов с фильтрами."""
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        if shop_id:
            params["shop_id"] = shop_id
        if courier_id:
            params["courier_id"] = courier_id
        if current is not None:
            params["current"] = str(current).lower()

        return await self._make_request("GET", "/orders/history", token=token, params=params)
