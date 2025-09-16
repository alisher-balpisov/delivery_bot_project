"""
Клиент для работы с пользователями через backend API
"""

from typing import Any

from .base_client import BaseApiClient


class UsersClient(BaseApiClient):
    """Клиент для работы с пользователями через backend API."""

    async def get_user_profile(self, telegram_id: int) -> dict[str, Any] | None:
        """Получить профиль пользователя по токену."""
        return await self._make_request("GET", "/users/me", telegram_id=telegram_id)

    async def get_all_couriers(self, telegram_id: int) -> list[Any] | None:
        """Получить всех курьеров."""
        return await self._make_request("GET", "/users/couriers", telegram_id=telegram_id)

    async def complete_registration(
        self, telegram_id: int, registration_data: dict
    ) -> dict[str, Any] | None:
        """Завершить регистрацию пользователя."""
        return await self._make_request(
            "POST",
            "/users/complete-registration",
            telegram_id=telegram_id,
            json_data=registration_data,
        )

    async def update_user_info(self, telegram_id: int, update_data: dict) -> dict[str, Any] | None:
        """Обновить информацию о пользователе."""
        return await self._make_request(
            "PUT", f"/users/{telegram_id}", telegram_id=telegram_id, json_data=update_data
        )
