"""
Клиент для работы со спорами через backend API
"""

from typing import Any, Dict, List, Optional

from .base_client import BaseApiClient


class DisputesClient(BaseApiClient):
    """Клиент для работы со спорами через backend API."""

    async def create_dispute(self, token: str, dispute_data: dict) -> Optional[Dict[str, Any]]:
        """Создать новый спор."""
        return await self._make_request(
            "POST", "/disputes/", token=token, json_data=dispute_data, expected_status=201
        )

    async def get_dispute_details(self, token: str, dispute_id: int) -> Optional[Dict[str, Any]]:
        """Получить детали спора по ID."""
        return await self._make_request("GET", f"/disputes/{dispute_id}", token=token)

    async def update_dispute_status(
        self, token: str, dispute_id: int, status_data: dict
    ) -> Optional[Dict[str, Any]]:
        """Обновить статус спора (для администраторов)."""
        return await self._make_request(
            "PATCH", f"/disputes/{dispute_id}", token=token, json_data=status_data
        )

    async def get_my_disputes(self, token: str) -> Optional[List[Any]]:
        """Получить споры пользователя (в зависимости от роли)."""
        return await self._make_request("GET", "/disputes/my", token=token)