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
        endpoint = "/admin/registration-codes"
        return await self._make_request(
            "POST", endpoint, token=token, json_data={"role": role}, expected_status=201
        )

    async def get_registration_codes(
        self,
        token: str,
        page: int = 1,
        limit: int = 10,
        role: str | None = None,
        is_used: bool | None = None,
    ) -> RequestResult:
        """Получить список регистрационных кодов с пагинацией."""
        params = {"page": page, "limit": limit}
        if role:
            params["role"] = role
        if is_used is not None:
            params["is_used"] = str(is_used).lower()

        return await self._make_request(
            "GET", "/admin/registration-codes", token=token, params=params
        )

    async def get_registration_code_details(self, token: str, code_id: int) -> RequestResult:
        """Получить детали кода регистрации."""
        return await self._make_request("GET", f"/admin/registration-codes/{code_id}", token=token)

    async def deactivate_registration_code(self, token: str, code_id: int) -> RequestResult:
        """Деактивировать код регистрации."""
        return await self._make_request(
            "POST", f"/admin/registration-codes/{code_id}/deactivate", token=token
        )

    async def get_registration_codes_stats(self, token: int) -> RequestResult:
        """Получить статистику регистрационных кодов."""
        return await self._make_request("GET", "/admin/registration-codes/stats", token=token)

    async def get_system_stats(self, token: str) -> RequestResult:
        """Получить системную статистику (общие метрики)."""
        return await self._make_request("GET", "/admin/system-stats", token=token)

    async def get_all_orders(
        self,
        token: str,
        page: int = 1,
        limit: int = 10,
        status: str | None = None,
        search: str | None = None,
        current: bool | None = None,
    ) -> RequestResult:
        """Получить список всех заказов (админ)."""
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if current is not None:
            params["current"] = str(current).lower()

        return await self._make_request("GET", "/admin/orders", token=token, params=params)

    async def get_order_details(self, token: str, order_id: int) -> RequestResult:
        """Получить детали заказа."""
        return await self._make_request("GET", f"/orders/{order_id}", token=token)

    async def update_order(self, token: str, order_id: int, data: dict) -> RequestResult:
        """Обновить заказ."""
        return await self._make_request("PATCH", f"/orders/{order_id}", token=token, json_data=data)
