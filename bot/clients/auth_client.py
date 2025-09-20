from backend.src.core.logging import get_logger

from .base_client import BaseApiClient, RequestResult

logger = get_logger(__name__)


class AuthClient(BaseApiClient):
    async def get_token(self, telegram_id: int) -> RequestResult:
        """
        Получает JWT токен для пользователя по его telegram_id.
        """
        return await self._make_request(
            "POST",
            "/auth/token",
            json_data={"telegram_id": telegram_id},
            expected_status=200,
        )

    async def auth_by_code(self, telegram_id: int, code: str) -> RequestResult:
        """
        Отправляет код для аутентификации и получения JWT токена.
        """
        return await self._make_request(
            "POST",
            "/auth/by-code",
            json_data={"telegram_id": telegram_id, "code": code},
            expected_status=200,
        )
