from .base_client import BaseApiClient, RequestResult


class UsersClient(BaseApiClient):
    """Клиент для работы с пользователями через backend API."""

    async def get_user_profile(self, telegram_id: int) -> RequestResult:
        """Получить профиль пользователя по telegram_id."""
        return await self._make_request("GET", "/users/me", telegram_id=telegram_id)

    async def get_all_couriers(self, telegram_id: int) -> RequestResult:
        """Получить всех курьеров."""
        return await self._make_request("GET", "/users/couriers", telegram_id=telegram_id)

    async def complete_registration(
        self, telegram_id: int, registration_data: dict
    ) -> RequestResult:
        """Завершить регистрацию пользователя."""
        return await self._make_request(
            "POST",
            "/users/complete-registration",
            telegram_id=telegram_id,
            json_data=registration_data,
        )

    async def update_user_info(self, telegram_id: int, update_data: dict) -> RequestResult:
        """Обновить информацию о пользователе."""
        return await self._make_request(
            "PUT", f"/users/{telegram_id}", telegram_id=telegram_id, json_data=update_data
        )
