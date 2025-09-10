"""
Клиент для авторизации через API backend
"""

from backend.src.core.logging import get_logger

from .base_client import BaseApiClient

logger = get_logger(__name__)


class AuthClient(BaseApiClient):
    """Клиент для авторизации через API backend."""

    async def bot_login(self, telegram_id: int) -> dict | None:
        """
        Авторизация пользователя через бота.

        Returns:
            {'access_token': str, 'user': dict, 'role': str} или None при ошибке.
        """
        response = await self._make_request(
            "POST",
            "/auth/bot-login",
            json_data={"telegram_id": telegram_id},
            expected_status=200,
        )
        if response and not response.get("success") is False:
            logger.info(f"✅ Успешная авторизация пользователя {telegram_id}")
            return response

        logger.warning(f"❌ Авторизация пользователя {telegram_id} не удалась.")
        return None

    async def validate_token(self, token: str) -> dict | None:
        """Проверить валидность токена."""
        user_data = await self._make_request("GET", "/users/me", token=token)

        if user_data and isinstance(user_data, dict) and not user_data.get("success") is False:
            return {"access_token": token, "user": user_data, "role": user_data.get("role")}

        logger.warning("❌ Токен недействителен.")
        return None

    async def register_user(
        self, telegram_id: int, code: str, role: str | None = None
    ) -> dict | None:
        """Зарегистрировать пользователя через код."""
        data = {"telegram_id": telegram_id, "code": code.strip()}
        if role:
            data["role"] = role

        response = await self._make_request(
            "POST", "/users/register", json_data=data, expected_status=200
        )

        if response and response.get("user_id"):
            logger.info(f"✅ Успешная регистрация пользователя {telegram_id}")
            return {
                "success": True,
                "role": response.get("role"),
                "user_id": response.get("user_id"),
                "is_registered": True,
            }

        detail = response.get("detail", "Ошибка сервера") if response else "Ошибка сервера"
        logger.warning(f"❌ Ошибка регистрации {telegram_id}: {detail}")
        return {"success": False, "detail": detail}
