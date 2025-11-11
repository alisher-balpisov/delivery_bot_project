from .base_client import BaseApiClient, RequestResult


class UsersClient(BaseApiClient):
    """Клиент для работы с пользователями через backend API."""

    async def get_user_profile(self, token: str) -> RequestResult:
        """Получить профиль пользователя по JWT токену."""
        return await self._make_request("GET", "/me", token=token)

    async def get_all_couriers(self, token: str) -> RequestResult:
        """Получить всех курьеров."""
        return await self._make_request("GET", "/couriers", token=token)

    async def complete_registration(self, token: str, registration_data: dict) -> RequestResult:
        """Завершить регистрацию пользователя."""
        return await self._make_request(
            "POST",
            "/complete-registration",
            token=token,
            json_data=registration_data,
        )

    async def update_user_info(self, token: str, update_data: dict) -> RequestResult:
        """Обновить информацию о пользователе."""
        return await self._make_request("PUT", "/me", token=token, json_data=update_data)
