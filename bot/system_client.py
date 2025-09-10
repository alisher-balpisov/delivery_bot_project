"""
Клиент для работы с системными операциями через backend API
"""

from typing import Any

from backend.src.core.logging import get_logger

from .base_client import BaseApiClient

logger = get_logger(__name__)


class SystemClient(BaseApiClient):
    """Клиент для системных операций через backend API."""

    async def health_check(self) -> dict[str, Any] | None:
        """Проверить статус системы (/health endpoint)."""
        try:
            full_url = f"{self.api_base_url}/health"
            response = await self.client.get(full_url)

            if response.is_success:
                return response.json()

            logger.warning(f"Health check failed with status {response.status_code}")
            return {"status": "error", "detail": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {"status": "error", "detail": str(e)}

    async def get_system_info(self) -> dict[str, Any] | None:
        """Получить системную информацию."""
        try:
            full_url = f"{self.api_base_url}/info"
            response = await self.client.get(full_url)

            if response.is_success:
                return response.json()

            logger.warning(f"System info failed with status {response.status_code}")
            return None

        except Exception as e:
            logger.error(f"System info error: {e}")
            return None
