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
        return await self._make_request("GET", "/health", expected_status=200)

    async def get_system_info(self) -> dict[str, Any] | None:
        return await self._make_request("GET", "/info", expected_status=200)
