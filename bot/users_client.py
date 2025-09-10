"""
Клиент для работы с пользователями через backend API
"""

from typing import Any, Dict, List, Optional

from .base_client import BaseApiClient


class UsersClient(BaseApiClient):
    """Клиент для работы с пользователями через backend API."""

    async def get_user_profile(self, token: str) -> Optional[Dict[str, Any]]:
        """Получить профиль пользователя по токену."""
        return await self._make_request("GET", "/users/me", token=token)

    async def get_all_couriers(self, token: str) -> Optional[List[Any]]:
        """Получить всех курьеров."""
        return await self._make_request("GET", "/users/couriers", token=token)

    async def complete_registration(
        self, token: str, registration_data: dict
    ) -> Optional[Dict[str, Any]]:
        """Завершить регистрацию пользователя."""
        return await self._make_request(
            "POST",
            "/users/complete-registration",
            token=token,
            json_data=registration_data,
        )

    async def update_user_info(self, token: str, update_data: dict) -> Optional[Dict[str, Any]]:
        """Обновить информацию о пользователе."""
        profile = await self.get_user_profile(token)
        if not (profile and profile.get("telegram_id")):
            return {"success": False, "detail": "Не удалось получить профиль для обновления"}

        telegram_id = profile["telegram_id"]
        return await self._make_request(
            "PUT", f"/users/{telegram_id}", token=token, json_data=update_data
        )
