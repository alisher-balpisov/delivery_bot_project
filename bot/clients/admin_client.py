from datetime import datetime
from typing import Literal

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

    # ==================== Споры (Disputes) ====================

    async def get_disputes(
        self,
        token: str,
        page: int = 1,
        limit: int = 10,
        status: str | None = None,
    ) -> RequestResult:
        """
        Получить список всех споров (только для админов).

        Args:
            token: Токен авторизации
            page: Номер страницы
            limit: Количество элементов на странице
            status: Фильтр по статусу (pending_review, in_review, resolved, cancelled)

        Returns:
            RequestResult с пагинированным списком споров
        """
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status

        return await self._make_request(
            "GET", "/disputes/admin/disputes", token=token, params=params
        )

    async def get_dispute_details(self, token: str, dispute_id: int) -> RequestResult:
        """
        Получить детали конкретного спора.

        Args:
            token: Токен авторизации
            dispute_id: ID спора

        Returns:
            RequestResult с деталями спора
        """
        return await self._make_request("GET", f"/disputes/{dispute_id}", token=token)

    async def update_dispute_status(self, token: str, dispute_id: int, data: dict) -> RequestResult:
        """
        Обновить статус спора (для администраторов).

        Args:
            token: Токен авторизации
            dispute_id: ID спора
            data: Данные для обновления (status, resolution_notes)

        Returns:
            RequestResult с обновленным спором
        """
        return await self._make_request(
            "PATCH", f"/disputes/{dispute_id}", token=token, json_data=data
        )

    async def export_shop_statistics(
        self,
        token: str,
        shop_id: int,
        date_from: datetime,
        date_to: datetime,
        stats_type: Literal["common", "advanced"] = "common",
        from_last_payment: bool = False,
    ) -> RequestResult:
        """Экспортировать статистику по магазину в Excel."""
        params = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "type": stats_type,
            "from_last_payment": str(from_last_payment).lower(),
        }

        return await self._make_request(
            "GET",
            f"/admin/shops/{shop_id}/stats/export",
            token=token,
            params=params,
            parse_json=False,  # ← НЕ парсим как JSON, получаем bytes
        )

    async def export_courier_statistics(
        self,
        token: str,
        courier_id: int,
        date_from: datetime,
        date_to: datetime,
        stats_type: Literal["common", "advanced"] = "common",
        from_last_payout: bool = False,
    ) -> RequestResult:
        """Экспортировать статистику по курьеру в Excel."""
        params = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "type": stats_type,
            "from_last_payout": str(from_last_payout).lower(),
        }

        return await self._make_request(
            "GET",
            f"/admin/couriers/{courier_id}/stats/export",
            token=token,
            params=params,
            parse_json=False,  # ← НЕ парсим как JSON
        )

    async def export_all_shops_statistics(
        self,
        token: str,
        date_from: datetime,
        date_to: datetime,
    ) -> RequestResult:
        """Экспортировать общую статистику всех магазинов в Excel."""
        params = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }

        return await self._make_request(
            "GET",
            "/admin/shops/stats/export",
            token=token,
            params=params,
            parse_json=False,  # ← НЕ парсим как JSON
        )
