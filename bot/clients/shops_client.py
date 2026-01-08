from typing import Any

from backend.src.shops.schemas import ShopCardResponse, ShopListResponse, ShopStatsResponse

from bot.clients.base_client import BaseApiClient


class ShopsClient(BaseApiClient):
    """Клиент для работы с магазинами."""

    async def get_shops(
        self,
        token: str,
        page: int = 1,
        limit: int = 10,
        status: str | None = None,
    ) -> ShopListResponse:
        """
        Получение списка магазинов.

        Args:
            token: Токен доступа
            page: Номер страницы
            limit: Количество элементов на странице
            status: Фильтр по статусу (active, inactive, etc.)
        """
        params: dict[str, Any] = {"page": page, "limit": limit}
        if status:
            params["status"] = status

        response = await self._make_request(
            method="GET",
            endpoint="/shops/",
            custom_headers=self._get_auth_headers(token),
            params=params,
        )
        if not response.success:
            # Handle error or return empty list/raise exception
            # For now, let's raise an exception or return empty if that's better
            # But BaseApiClient usually handles logging.
            # Let's assume we want to raise if not success for now, or return empty.
            # Better to raise to let global handler catch it or handle gracefully.
            # But here we expect data.
            raise Exception(response.detail)

        return ShopListResponse.model_validate(response.data)

    async def get_shop_by_id(
        self,
        token: str,
        shop_id: int,
    ) -> ShopCardResponse:
        """
        Получение детальной информации о магазине.

        Args:
            token: Токен доступа
            shop_id: ID магазина

        Returns:
            ShopCardResponse: Детальная информация о магазине
        """
        response = await self._make_request(
            method="GET",
            endpoint=f"/shops/{shop_id}",
            custom_headers=self._get_auth_headers(token),
        )
        if not response.success:
            raise Exception(response.detail)

        return ShopCardResponse.model_validate(response.data)

    async def get_shop_stats(self, token: str) -> ShopStatsResponse:
        """
        Получение статистики магазина.

        Args:
            token: Токен доступа

        Returns:
            ShopStatsResponse: Статистика магазина
        """
        response = await self._make_request(
            method="GET",
            endpoint="/shops/stats",
            custom_headers=self._get_auth_headers(token),
        )
        if not response.success:
            raise Exception(response.detail)

        return ShopStatsResponse.model_validate(response.data)

    async def update_shop_profile(
        self,
        token: str,
        data: dict,
    ) -> ShopCardResponse:
        """
        Обновление профиля магазина.

        Args:
            token: Токен доступа
            data: Данные для обновления
        """
        response = await self._make_request(
            method="PATCH",
            endpoint="/shops/me",
            custom_headers=self._get_auth_headers(token),
            json_data=data,
        )
        if not response.success:
            raise Exception(response.detail)

        return ShopCardResponse.model_validate(response.data)
