"""
Клиент для работы с заказами через backend API
"""

from typing import Any

from .base_client import BaseApiClient


class OrdersClient(BaseApiClient):
    """Клиент для работы с заказами через backend API."""

    async def create_order(self, telegram_id: int, order_data: dict) -> dict[str, Any] | None:
        """Создать новый заказ."""
        return await self._make_request(
            "POST",
            "/orders/",
            telegram_id=telegram_id,
            json_data=order_data,
            expected_status=201,
        )

    async def get_order_details(self, telegram_id: int, order_id: int) -> dict[str, Any] | None:
        """Получить детали заказа по ID."""
        return await self._make_request("GET", f"/orders/{order_id}", telegram_id=telegram_id)

    async def get_user_orders(self, telegram_id: int) -> list[Any] | None:
        """Получить заказы пользователя (в зависимости от роли)."""
        return await self._make_request("GET", "/orders/my", telegram_id=telegram_id)

    async def update_order_status(
        self, telegram_id: int, order_id: int, status_data: dict
    ) -> dict[str, Any] | None:
        """Обновить статус заказа."""
        return await self._make_request(
            "PATCH", f"/orders/{order_id}", telegram_id=telegram_id, json_data=status_data
        )

    async def get_available_orders(self, telegram_id: int) -> list[Any] | None:
        """Получить доступные заказы (для курьеров)."""
        return await self._make_request("GET", "/orders/available", telegram_id=telegram_id)
