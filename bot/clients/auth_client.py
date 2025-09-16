"""
Клиент для авторизации через API backend
"""

from backend.src.core.logging import get_logger

from bot.utils import parse_user_role

from .base_client import BaseApiClient

logger = get_logger(__name__)


class AuthClient(BaseApiClient):
    async def auth_by_code(self, telegram_id: int, code: str) -> dict | None:
        response = await self._make_request(
            "POST",
            "/auth/by-code",
            json_data={"telegram_id": telegram_id, "code": code},
            expected_status=200,
        )
        if response and response.get("success") is True:
            logger.info(f"✅ Успешная авторизация пользователя {telegram_id}")
            # Преобразуем строковую роль в Enum
            if "user" in response and "role" in response["user"]:
                response["user"]["role"] = parse_user_role(response["user"]["role"])
            return response
        logger.warning(f"❌ Авторизация пользователя {telegram_id} не удалась.")
        return response
