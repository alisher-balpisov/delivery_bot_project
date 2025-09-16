from backend.src.core.logging import get_logger

from .base_client import BaseApiClient, RequestResult

logger = get_logger(__name__)


class SystemClient(BaseApiClient):
    """Клиент для системных операций через backend API."""

    async def health_check(self) -> RequestResult:
        """Проверка состояния API."""
        return await self._make_request("GET", "/health", expected_status=200)

    async def get_system_info(self) -> RequestResult:
        """Получение системной информации."""
        return await self._make_request("GET", "/info", expected_status=200)
