"""
Клиент для администраторских функций через backend API
"""

from typing import Any

from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from .base_client import BaseApiClient

logger = get_logger(__name__)


class AdminClient(BaseApiClient):
    """Клиент для администраторских функций через backend API."""

    async def create_registration_code(
        self, telegram_id: int, role: UserRole
    ) -> dict[str, Any] | None:
        """
        Создать новый регистрационный код для указанной роли.

        Args:
            telegram_id: Telegram ID администратора.
            role: Роль для которой создается код.

        Returns:
            Созданный код или None при ошибке.
        """

        endpoint = f"/admin/create-code/{role.value}"
        result = await self._make_request(
            "POST", endpoint, telegram_id=telegram_id, expected_status=201
        )

        if result:
            logger.info(f"✅ Регистрационный код для роли {role.value} создан")
        return result

    async def get_all_registration_codes(self, telegram_id: int) -> list[Any] | None:
        """Получить все регистрационные коды."""
        return await self._make_request("GET", "/admin/registration-codes", telegram_id=telegram_id)

    async def get_registration_codes_by_role(self, telegram_id: int, role: str) -> list[Any] | None:
        """Получить регистрационные коды по роли."""
        return await self._make_request(
            "GET", f"/admin/registration-codes/{role}", telegram_id=telegram_id
        )

    async def get_registration_codes_stats(self, telegram_id: int) -> dict[str, Any] | None:
        """Получить статистику регистрационных кодов."""
        return await self._make_request(
            "GET", "/admin/registration-codes/stats", telegram_id=telegram_id
        )

    async def get_system_stats(self, telegram_id: int) -> dict[str, Any] | None:
        """Получить системную статистику (общие метрики)."""
        return await self._make_request("GET", "/admin/system-stats", telegram_id=telegram_id)
