from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from .base_client import BaseApiClient, RequestResult

logger = get_logger(__name__)


class AdminClient(BaseApiClient):
    """Клиент для администраторских функций через backend API."""

    async def create_registration_code(self, token: str, role: UserRole) -> RequestResult:
        """
        Создать новый регистрационный код для указанной роли.
        """
        endpoint = f"/admin/create-code/{role.value}"
        return await self._make_request("POST", endpoint, token=token, expected_status=201)

    async def get_all_registration_codes(self, token: str) -> RequestResult:
        """Получить все регистрационные коды."""
        return await self._make_request("GET", "/admin/registration-codes", token=token)

    async def get_registration_codes_by_role(self, token: int, role: str) -> RequestResult:
        """Получить регистрационные коды по роли."""
        return await self._make_request("GET", f"/admin/registration-codes/{role}", token=token)

    async def get_registration_codes_stats(self, token: int) -> RequestResult:
        """Получить статистику регистрационных кодов."""
        return await self._make_request("GET", "/admin/registration-codes/stats", token=token)

    async def get_system_stats(self, token: str) -> RequestResult:
        """Получить системную статистику (общие метрики)."""
        return await self._make_request("GET", "/admin/system-stats", token=token)
