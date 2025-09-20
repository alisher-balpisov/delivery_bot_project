from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx
from backend.src.core.config import settings
from backend.src.core.logging import get_logger

from bot.constants import HttpMethod, error_map
from bot.messages import BaseClientMessages

logger = get_logger(__name__)


@dataclass
class RequestResult:
    success: bool
    data: Any | None = None
    detail: Any | None = None
    status_code: int | None = None


class ConnectionPool:
    _instance: ClassVar[ConnectionPool | None] = None
    _client: httpx.AsyncClient | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                headers={"User-Agent": "DeliveryBot/1.0"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class BaseApiClient:
    def __init__(
        self,
        pool: ConnectionPool,
        api_base_url: str | None = None,
        timeout: float = 10.0,
    ):
        if timeout <= 0:
            raise ValueError("Timeout must be a positive number.")
        if api_base_url and not (
            api_base_url.startswith("http://") or api_base_url.startswith("https://")
        ):
            raise ValueError("api_base_url must be a valid HTTP or HTTPS URL.")
        self.pool = pool
        self.api_base_url = api_base_url or f"http://{settings.api_host}:{settings.api_port}"
        self.api_prefix = settings.api_prefix
        self.timeout = timeout
        self.rng = random.SystemRandom()

    async def _make_request(
        self,
        method: str | HttpMethod,
        endpoint: str,
        token: str | None = None,
        json_data: dict[str, Any] | None = None,
        custom_headers: dict[str, str] | None = None,
        expected_status: int = 200,
        retry_count: int = 3,
    ) -> RequestResult:
        """
        Выполняет HTTP-запрос, координируя подготовку, выполнение с ретраями и обработку ответа.
        """
        method_str, url, headers = self._prepare_request_params(
            method, endpoint, token, custom_headers
        )
        return await self._execute_with_retry(
            method_str, url, headers, json_data, expected_status, retry_count
        )

    def _prepare_request_params(
        self,
        method: str | HttpMethod,
        endpoint: str,
        token: str | None,
        custom_headers: dict[str, str] | None,
    ) -> tuple[str, str, dict[str, str]]:
        """Готовит и валидирует URL, заголовки и HTTP-метод."""
        method_str = self._validate_method(method)

        if not isinstance(endpoint, str) or not endpoint:
            raise ValueError("Endpoint must be a non-empty string")

        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        url = f"{self.api_base_url}{self.api_prefix}{endpoint}"

        headers = custom_headers.copy() if custom_headers else {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return method_str, url, headers

    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_data: dict[str, Any] | None,
        expected_status: int,
        retry_count: int,
    ) -> RequestResult:
        """Выполняет запрос с логикой повторных попыток при сбоях."""
        for attempt in range(retry_count):
            try:
                response = await self._execute_request(method, url, headers, json_data)
                result = self._handle_response(response, expected_status)

                if result.success or not self._should_retry(
                    response.status_code, attempt, retry_count
                ):
                    return result

                logger.warning(
                    BaseClientMessages.SERVER_ERROR_RETRY.format(
                        response.status_code, attempt + 1, retry_count
                    )
                )
                delay = self._calculate_backoff_delay(attempt)
                await asyncio.sleep(delay)

            except (httpx.TimeoutException, httpx.RequestError) as e:
                if self._should_retry_on_exception(e, attempt, retry_count):
                    self._log_retry_exception(e, url, attempt, retry_count)
                    await asyncio.sleep(1.0 + self.rng.uniform(0, 0.1))
                    continue
                return self._handle_final_exception(e, method, url)

        return RequestResult(
            success=False, detail=BaseClientMessages.RETRIES_EXCEEDED, status_code=503
        )

    async def _execute_request(
        self, method: str, url: str, headers: dict[str, str], json_data: dict[str, Any] | None
    ) -> httpx.Response:
        """Непосредственно выполняет HTTP-запрос."""
        client = await self.pool.get_client()
        return await client.request(
            method, url, headers=headers, json=json_data, timeout=self.timeout
        )

    def _validate_method(self, method: str | HttpMethod) -> str:
        """Валидирует и нормализует HTTP-метод."""
        if isinstance(method, HttpMethod):
            return method.value
        if isinstance(method, str):
            method_upper = method.upper()
            if method_upper in [m.value for m in HttpMethod]:
                return method_upper
        raise ValueError(f"Unsupported or invalid HTTP method: {method}")

    def _should_retry(self, status_code: int, attempt: int, retry_count: int) -> bool:
        """Определяет, нужно ли повторять запрос на основе статуса ответа."""
        return status_code >= 500 and attempt < retry_count - 1

    def _should_retry_on_exception(self, exc: Exception, attempt: int, retry_count: int) -> bool:
        """Определяет, нужно ли повторять запрос при исключении."""
        return (
            isinstance(exc, (httpx.TimeoutException, httpx.RequestError))
            and attempt < retry_count - 1
        )

    def _log_retry_exception(
        self, exc: Exception, url: str, attempt: int, retry_count: int
    ) -> None:
        """Логирует исключение при повторной попытке."""
        if isinstance(exc, httpx.TimeoutException):
            logger.warning(BaseClientMessages.TIMEOUT_RETRY.format(url, attempt + 1, retry_count))
        elif isinstance(exc, httpx.RequestError):
            logger.warning(
                BaseClientMessages.NETWORK_ERROR_RETRY.format(url, attempt + 1, retry_count)
            )

    def _handle_final_exception(self, exc: Exception, method: str, url: str) -> RequestResult:
        """Обрабатывает финальное исключение после всех попыток."""
        if isinstance(exc, httpx.TimeoutException):
            logger.error(BaseClientMessages.TIMEOUT_ERROR.format(method, url))
            return RequestResult(
                success=False, detail=BaseClientMessages.TIMEOUT_EXCEEDED, status_code=408
            )
        elif isinstance(exc, httpx.RequestError):
            logger.error(BaseClientMessages.NETWORK_ERROR.format(method, url, exc))
            return RequestResult(
                success=False, detail=BaseClientMessages.NETWORK_ERROR_SIMPLE, status_code=503
            )

        logger.error(
            BaseClientMessages.UNEXPECTED_REQUEST_ERROR.format(method, url, exc), exc_info=True
        )
        return RequestResult(
            success=False, detail=BaseClientMessages.UNEXPECTED_CLIENT_ERROR, status_code=500
        )

    def _handle_response(self, response: httpx.Response, expected_status: int) -> RequestResult:
        """Обрабатывает HTTP-ответ и возвращает структурированный результат."""
        if response.status_code == expected_status:
            return self._parse_success_response(response)

        try:
            error_data = response.json()
            detail = error_data.get("detail", response.text[:200])
        except (ValueError, TypeError):
            detail = response.text[:200] or error_map.get(response.status_code, "Unknown Error")

        logger.warning(
            BaseClientMessages.HTTP_ERROR.format(response.status_code, response.request.url, detail)
        )
        return RequestResult(success=False, detail=detail, status_code=response.status_code)

    def _parse_success_response(self, response: httpx.Response) -> RequestResult:
        """Парсит успешный JSON-ответ."""
        try:
            data = response.json()
            return RequestResult(success=True, data=data, status_code=response.status_code)
        except (ValueError, TypeError):
            # Если тело ответа пустое, но статус успешный - это тоже успех
            if not response.text.strip():
                return RequestResult(success=True, data=None, status_code=response.status_code)
            logger.warning(f"Не удалось распарсить JSON из успешного ответа: {response.text[:200]}")
            return RequestResult(
                success=False,
                detail=BaseClientMessages.INVALID_JSON,
                status_code=response.status_code,
            )

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Вычисляет задержку для backoff с jitter."""
        base_delay = min(0.5 * (2**attempt), 5.0)  # Экспоненциальная задержка с максимумом 5с
        jitter = self.rng.uniform(0, 0.2 * base_delay)
        return base_delay + jitter
