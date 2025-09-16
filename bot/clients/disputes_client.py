from .base_client import BaseApiClient, RequestResult


class DisputesClient(BaseApiClient):
    """Клиент для работы со спорами через backend API."""

    async def create_dispute(self, telegram_id: int, dispute_data: dict) -> RequestResult:
        """Создать новый спор."""
        return await self._make_request(
            "POST",
            "/disputes/",
            telegram_id=telegram_id,
            json_data=dispute_data,
            expected_status=201,
        )

    async def get_dispute_details(self, telegram_id: int, dispute_id: int) -> RequestResult:
        """Получить детали спора по ID."""
        return await self._make_request("GET", f"/disputes/{dispute_id}", telegram_id=telegram_id)

    async def update_dispute_status(
        self, telegram_id: int, dispute_id: int, status_data: dict
    ) -> RequestResult:
        """Обновить статус спора (для администраторов)."""
        return await self._make_request(
            "PATCH", f"/disputes/{dispute_id}", telegram_id=telegram_id, json_data=status_data
        )

    async def get_my_disputes(self, telegram_id: int) -> RequestResult:
        """Получить споры пользователя (в зависимости от роли)."""
        return await self._make_request("GET", "/disputes/my", telegram_id=telegram_id)
