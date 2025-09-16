from backend.src.core.logging import get_logger

from .base_client import BaseApiClient, RequestResult

logger = get_logger(__name__)


class AuthClient(BaseApiClient):
    async def auth_by_code(self, telegram_id: int, code: str) -> RequestResult:
        return await self._make_request(
            "POST",
            "/auth/by-code",
            json_data={"telegram_id": telegram_id, "code": code},
            expected_status=200,
        )
