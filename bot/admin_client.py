"""
Клиент для администраторских функций через backend API
"""

from typing import Any, List, Optional

from backend.src.core.logging import get_logger

from .base_client import BaseApiClient

logger = get_logger(__name__)


class AdminClient(BaseApiClient):
    """Клиент для администраторских функций через backend API."""

    async def create_registration_code(self, token: str, role: str) -> Optional[dict[str, Any]]:
        """
        Создать новый регистрационный код для указанной роли.

        Args:
            token: JWT токен авторизации.
            role: Роль для которой создается код.

        Returns:
            Созданный код или None при ошибке.
        """
        valid_roles = ["admin", "shop", "courier"]
        if role not in valid_roles:
            logger.warning(f"❌ Неверная роль: {role}")
            return {
                "success": False,
                "detail": f"Неверная роль. Допустимые: {', '.join(valid_roles)}",
            }

        endpoint = f"/admin/create-code/{role}"
        result = await self._make_request("POST", endpoint, token=token, expected_status=201)

        if result and result.get("success") is not False:
            logger.info(f"✅ Регистрационный код для роли {role} создан")
        return result

    async def get_all_registration_codes(self, token: str) -> Optional[List[Any]]:
        """Получить все регистрационные коды."""
        return await self._make_request("GET", "/admin/registration-codes", token=token)

    async def get_registration_codes_by_role(self, token: str, role: str) -> Optional[List[Any]]:
        """Получить регистрационные коды по роли."""
        return await self._make_request("GET", f"/admin/registration-codes/{role}", token=token)

    async def get_registration_codes_stats(self, token: str) -> Optional[dict[str, Any]]:
        """Получить статистику регистрационных кодов."""
        return await self._make_request("GET", "/admin/registration-codes/stats", token=token)

    async def get_system_stats(self, token: str) -> Optional[dict[str, Any]]:
        """Получить системную статистику (общие метрики)."""
        return await self._make_request("GET", "/admin/system-stats", token=token)
