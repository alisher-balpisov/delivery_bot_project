from typing import Any

from .base_client import BaseApiClient, RequestResult


class CouriersClient(BaseApiClient):
    """Клиент для работы с курьерами через backend API."""

    async def get_couriers(
        self,
        token: str,
        page: int = 1,
        size: int = 10,
        status: str | None = None,
    ) -> RequestResult:
        """
        Получить список курьеров с пагинацией и фильтрацией.

        Args:
            token: JWT токен доступа
            page: Номер страницы
            size: Размер страницы
            status: Фильтр по статусу (active, inactive, on_shift, all)
        """
        params: dict[str, Any] = {"page": page, "size": size}
        if status:
            params["status"] = status

        return await self._make_request("GET", "/couriers/", token=token, params=params)

    async def get_courier_details(self, token: str, courier_id: int) -> RequestResult:
        """Получить детальную информацию о курьере."""
        return await self._make_request("GET", f"/couriers/{courier_id}", token=token)
