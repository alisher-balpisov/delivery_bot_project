"""
Клиент для работы с системными операциями через backend API
"""

from typing import Any, Dict, Optional

from .base_client import BaseApiClient


class SystemClient(BaseApiClient):
    """Клиент для системных операций через backend API."""

    async def health_check(self) -> Optional[Dict[str, Any]]:
        """Проверить статус системы (/health endpoint)."""
        # health check не использует стандартный префикс /api/v1
        full_url = f"{self.api_base_url}/health"
        response = await self.client.get(full_url)
        response.raise_for_status()
        return response.json()

    async def get_system_info(self) -> Optional[Dict[str, Any]]:
        """Получить системную информацию."""
        # Этот эндпоинт также может быть без префикса
        full_url = f"{self.api_base_url}/info"
        response = await self.client.get(full_url)
        if response.is_success:
            return response.json()
        return None
