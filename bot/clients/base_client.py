import asyncio
from typing import Any, ClassVar, Optional

import httpx
from backend.src.core.config import settings
from backend.src.core.logging import get_logger

from bot.constants import error_map
from bot.messages import BaseClientMessages

logger = get_logger(__name__)


class ConnectionPool:
    """Singleton пул соединений для всех API клиентов."""

    _instance: ClassVar[Optional["ConnectionPool"]] = None
    _client: httpx.AsyncClient | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self) -> httpx.AsyncClient:
        """Получить или создать клиент из пула."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                headers={"User-Agent": "DeliveryBot/1.0"},
            )
        return self._client

    async def close(self):
        """Закрыть пул соединений."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Глобальный пул соединений
connection_pool = ConnectionPool()


class BaseApiClient:
    """Базовый класс для API клиентов с улучшенным управлением соединениями."""

    def __init__(self, api_base_url: str | None = None, timeout: float = 10.0):
        """Инициализирует базовый API клиент."""
        self.api_base_url = api_base_url or f"http://{settings.api_host}:{settings.api_port}"
        self.api_prefix = settings.api_prefix
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Не закрываем глобальный пул здесь
        pass

    def _build_url(self, endpoint: str) -> str:
        """Строит полный URL для API endpoint'а."""
        return f"{self.api_base_url}{self.api_prefix}{endpoint}"

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        telegram_id: int | None = None,
        json_data: dict[str, Any] | None = None,
        custom_headers: dict[str, str] | None = None,
        expected_status: int = 200,
        retry_count: int = 3,
    ) -> dict[str, Any] | list[Any] | None:
        """
        Унифицированный метод для выполнения HTTP запросов с retry логикой.
        """
        url = self._build_url(endpoint)
        headers = custom_headers or {}
        if telegram_id:
            headers["X-Telegram-ID"] = str(telegram_id)

        client = await connection_pool.get_client()

        for attempt in range(retry_count):
            try:
                response = await client.request(
                    method, url, headers=headers, json=json_data, timeout=self.timeout
                )

                if response.status_code == expected_status:
                    try:
                        return response.json()
                    except ValueError:
                        logger.warning(f"Не удалось распарсить JSON из ответа: {response.text}")
                        return {"success": False, "detail": BaseClientMessages.INVALID_JSON}

                # Обработка ошибок клиента (не повторяем)
                if 400 <= response.status_code < 500:
                    try:
                        error_details = response.json().get("detail", response.text)
                    except ValueError:
                        error_details = response.text

                    # Приоритет отдаем сообщению от API
                    error_message = error_details or error_map.get(
                        response.status_code,
                        BaseClientMessages.CLIENT_ERROR.format(response.status_code),
                    )

                    logger.warning(
                        BaseClientMessages.HTTP_ERROR.format(
                            response.status_code, endpoint, error_message
                        )
                    )
                    return {"success": False, "detail": error_message}

                # Серверные ошибки (повторяем)
                if response.status_code >= 500:
                    if attempt < retry_count - 1:
                        logger.warning(
                            BaseClientMessages.SERVER_ERROR_RETRY.format(
                                response.status_code, attempt + 1, retry_count
                            )
                        )
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                        continue

                logger.error(
                    BaseClientMessages.UNEXPECTED_STATUS.format(response.status_code, endpoint)
                )
                return {
                    "success": False,
                    "detail": BaseClientMessages.SERVER_ERROR.format(response.status_code),
                }

            except httpx.TimeoutException:
                if attempt < retry_count - 1:
                    logger.warning(
                        BaseClientMessages.TIMEOUT_RETRY.format(endpoint, attempt + 1, retry_count)
                    )
                    await asyncio.sleep(1)
                    continue
                logger.error(BaseClientMessages.TIMEOUT_ERROR.format(method, url))
                return {"success": False, "detail": BaseClientMessages.TIMEOUT_EXCEEDED}

            except httpx.RequestError as e:
                if attempt < retry_count - 1:
                    logger.warning(
                        BaseClientMessages.NETWORK_ERROR_RETRY.format(
                            endpoint, attempt + 1, retry_count
                        )
                    )
                    await asyncio.sleep(1)
                    continue
                logger.error(BaseClientMessages.NETWORK_ERROR.format(method, url, e))
                return {"success": False, "detail": BaseClientMessages.NETWORK_ERROR_SIMPLE}

            except Exception as e:
                logger.error(
                    BaseClientMessages.UNEXPECTED_REQUEST_ERROR.format(method, url, e),
                    exc_info=True,
                )
                return {"success": False, "detail": BaseClientMessages.UNEXPECTED_CLIENT_ERROR}

        return {"success": False, "detail": BaseClientMessages.RETRIES_EXCEEDED}
