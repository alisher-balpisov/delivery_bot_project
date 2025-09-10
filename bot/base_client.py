"""
Базовый клиент для API взаимодействия с backend
Унифицированная логика для всех клиентских классов
"""

from typing import Any, Dict, List, Optional, Union

import httpx
from backend.src.core.config import settings
from backend.src.core.logging import get_logger

logger = get_logger(__name__)


class BaseApiClient:
    """Базовый класс для API клиентов."""

    def __init__(self, api_base_url: Optional[str] = None, timeout: float = 10.0):
        """
        Инициализирует базовый API клиент.
        """
        self.api_base_url = api_base_url or f"http://{settings.api_host}:{settings.api_port}"
        self.api_prefix = settings.api_prefix
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _build_url(self, endpoint: str) -> str:
        """Строит полный URL для API endpoint'а."""
        return f"{self.api_base_url}{self.api_prefix}{endpoint}"

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        token: Optional[str] = None,
        json_data: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        expected_status: int = 200,
    ) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """
        Унифицированный метод для выполнения HTTP запросов.
        Возвращает ответ как словарь/список или словарь с ошибкой.
        """
        url = self._build_url(endpoint)
        headers = custom_headers or {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = await self.client.request(method, url, headers=headers, json=json_data)

            # Успешный ответ
            if response.status_code == expected_status:
                try:
                    return response.json()
                except ValueError:
                    logger.warning(f"Не удалось распарсить JSON из ответа: {response.text}")
                    return {"success": False, "detail": "Некорректный JSON ответ от сервера."}

            # Обработка ошибок
            try:
                error_details = response.json().get("detail", response.text)
            except ValueError:
                error_details = response.text

            error_map = {
                400: "Неверные данные",
                401: "Ошибка авторизации",
                403: "Недостаточно прав",
                404: "Ресурс не найден",
            }
            if response.status_code in error_map:
                logger.warning(f"❌ HTTP {response.status_code} для {endpoint}: {error_details}")
                return {"success": False, "detail": error_map[response.status_code]}

            logger.error(
                f"💥 Неожиданный статус код: {response.status_code} для {endpoint} - {error_details}"
            )
            return {"success": False, "detail": f"Ошибка сервера: {response.status_code}"}

        except httpx.RequestError as e:
            logger.error(f"❌ Ошибка сети при запросе {method} {url}: {e}")
            return {"success": False, "detail": "Ошибка сети"}
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка при запросе {method} {url}: {e}", exc_info=True)
            return {"success": False, "detail": "Неожиданная ошибка на стороне клиента"}
