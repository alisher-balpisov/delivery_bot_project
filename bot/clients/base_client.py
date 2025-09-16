from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

import httpx
from backend.src.core.config import settings
from backend.src.core.logging import get_logger

from bot.constants import error_map
from bot.messages import BaseClientMessages

logger = get_logger(__name__)


class HttpMethod(Enum):
    """Перечисление HTTP методов для лучшей типизации."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class RequestResult:
    """Структура для результатов HTTP запросов."""

    success: bool
    data: Any | None = None
    detail: str | None = None
    status_code: int | None = None


class ConnectionPool:
    """Singleton пул соединений для всех API клиентов."""

    _instance: ClassVar[ConnectionPool | None] = None
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


class BaseApiClient:
    """Базовый класс для API клиентов с улучшенным управлением соединениями."""

    def __init__(
        self,
        pool: ConnectionPool,
        api_base_url: str | None = None,
        timeout: float = 10.0,
    ):
        """Инициализирует базовый API клиент.

        Args:
            api_base_url: Базовый URL API. Если None, используется значение из настроек.
                Должен начинаться с 'http://' или 'https://' если указан.
            timeout: Таймаут для HTTP запросов в секундах. Должен быть положительным числом.

        Raises:
            ValueError: Если timeout не положительный или api_base_url имеет неверный формат.
        """
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

    async def __aenter__(self):
        """Вход в контекстный менеджер. Возвращает экземпляр клиента."""
        logger.debug("Entering BaseApiClient context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджер. Глобальный пул соединений не закрывается здесь."""
        logger.debug("Exiting BaseApiClient context.")
        pass

    def _build_url(self, endpoint: str) -> str:
        """Строит полный URL для API endpoint'а."""
        if not isinstance(endpoint, str):
            raise ValueError("Endpoint must be a string")
        if not endpoint:
            raise ValueError("Endpoint cannot be empty")
        return f"{self.api_base_url}{self.api_prefix}{endpoint}"

    async def _make_request(
        self,
        method: str | HttpMethod,
        endpoint: str,
        telegram_id: int | None = None,
        json_data: dict[str, Any] | None = None,
        custom_headers: dict[str, str] | None = None,
        expected_status: int = 200,
        retry_count: int = 3,
    ) -> RequestResult:
        """
        Унифицированный метод для выполнения HTTP запросов с retry логикой.
        """
        url, headers = self._prepare_request(endpoint, telegram_id, custom_headers)
        method_str = self._validate_method(method)
        client = await self.pool.get_client()

        for attempt in range(retry_count):
            try:
                response = await client.request(
                    method_str, url, headers=headers, json=json_data, timeout=self.timeout
                )

                result = self._handle_response(
                    response, expected_status, endpoint, attempt, retry_count
                )
                if result.success or not self._should_retry(
                    response.status_code, attempt, retry_count
                ):
                    result.status_code = response.status_code
                    return result

                delay = self._calculate_backoff_delay(attempt, response.status_code)
                await asyncio.sleep(delay)

            except (httpx.TimeoutException, httpx.RequestError, Exception) as e:
                if attempt < retry_count - 1 and self._should_retry_on_exception(e):
                    await self._handle_retry_exception(e, endpoint, attempt, retry_count)
                    continue
                return self._handle_final_exception(e, method, url)

        return RequestResult(
            success=False, detail=BaseClientMessages.RETRIES_EXCEEDED, status_code=503
        )

    def _prepare_request(
        self, endpoint: str, telegram_id: int | None, custom_headers: dict[str, str] | None
    ) -> tuple[str, dict[str, str]]:
        """Подготавливает URL и заголовки для запроса."""
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        url = self._build_url(endpoint)
        headers = custom_headers.copy() if custom_headers else {}
        if telegram_id:
            headers["X-Telegram-ID"] = str(telegram_id)
        return url, headers

    def _validate_method(self, method: str | HttpMethod) -> str:
        """Валидирует и нормализует HTTP метод."""
        if isinstance(method, HttpMethod):
            return method.value
        if isinstance(method, str):
            method_upper = method.upper()
            if method_upper in [m.value for m in HttpMethod]:
                return method_upper
            raise ValueError(f"Unsupported HTTP method: {method}")
        raise ValueError(f"Method must be str or HttpMethod, got {type(method)}")

    def _should_retry_on_exception(self, exc: Exception) -> bool:
        """Определяет, нужно ли повторять запрос при исключении."""
        return isinstance(exc, (httpx.TimeoutException, httpx.RequestError))

    async def _handle_retry_exception(
        self, exc: Exception, endpoint: str, attempt: int, retry_count: int
    ) -> None:
        """Обрабатывает исключение при retry."""
        if isinstance(exc, httpx.TimeoutException):
            logger.warning(
                BaseClientMessages.TIMEOUT_RETRY.format(endpoint, attempt + 1, retry_count)
            )
        elif isinstance(exc, httpx.RequestError):
            logger.warning(
                BaseClientMessages.NETWORK_ERROR_RETRY.format(endpoint, attempt + 1, retry_count)
            )
        await asyncio.sleep(1.0 + self.rng.uniform(0, 0.1))

    def _handle_final_exception(
        self, exc: Exception, method: str | HttpMethod, url: str
    ) -> RequestResult:
        """Обрабатывает финальное исключение после всех попыток."""
        method_str = self._validate_method(method)
        if isinstance(exc, httpx.TimeoutException):
            logger.error(BaseClientMessages.TIMEOUT_ERROR.format(method_str, url))
            return RequestResult(
                success=False,
                detail=BaseClientMessages.TIMEOUT_EXCEEDED,
                status_code=408,
            )
        elif isinstance(exc, httpx.RequestError):
            logger.error(BaseClientMessages.NETWORK_ERROR.format(method_str, url, exc))
            return RequestResult(
                success=False,
                detail=BaseClientMessages.NETWORK_ERROR_SIMPLE,
                status_code=503,
            )
        else:
            logger.error(
                BaseClientMessages.UNEXPECTED_REQUEST_ERROR.format(method_str, url, exc),
                exc_info=True,
            )
            return RequestResult(
                success=False,
                detail=BaseClientMessages.UNEXPECTED_CLIENT_ERROR,
                status_code=500,
            )

    def _handle_response(
        self,
        response: httpx.Response,
        expected_status: int,
        endpoint: str,
        attempt: int,
        retry_count: int,
    ) -> RequestResult:
        """Обрабатывает HTTP ответ и возвращает структурированный результат."""
        if response.status_code == expected_status:
            return self._parse_success_response(response)

        if 300 <= response.status_code < 400:
            logger.warning(f"Redirect status {response.status_code} for {endpoint}")
            return RequestResult(
                success=False,
                detail=f"Redirect: {response.status_code}",
                status_code=response.status_code,
            )

        if 400 <= response.status_code < 500:
            return self._handle_client_error(response, endpoint)

        if response.status_code >= 500:
            # --- ИЗМЕНЕНИЕ: Передаем attempt и retry_count дальше ---
            return self._handle_server_error(response, endpoint, attempt, retry_count)

        logger.error(BaseClientMessages.UNEXPECTED_STATUS.format(response.status_code, endpoint))
        return RequestResult(
            success=False,
            detail=BaseClientMessages.SERVER_ERROR.format(response.status_code),
            status_code=response.status_code,
        )

    def _parse_success_response(self, response: httpx.Response) -> RequestResult:
        """Парсит успешный JSON ответ."""
        try:
            data = response.json()
            return RequestResult(success=True, data=data, status_code=response.status_code)
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Не удалось распарсить JSON из ответа: {response.text[:200]}... Ошибка: {e}"
            )
            return RequestResult(
                success=False,
                detail=BaseClientMessages.INVALID_JSON,
                status_code=response.status_code,
            )

    def _handle_client_error(self, response: httpx.Response, endpoint: str) -> RequestResult:
        """Обрабатывает клиентские ошибки (4xx)."""
        try:
            json_data = response.json()
            error_details = json_data.get("detail") if isinstance(json_data, dict) else None
        except (ValueError, TypeError):
            error_details = None

        if not error_details and response.text:
            error_details = response.text[:500]  # Ограничиваем длину для логирования
        elif not error_details:
            error_details = f"HTTP {response.status_code}"

        error_message = error_details or error_map.get(
            response.status_code,
            BaseClientMessages.CLIENT_ERROR.format(response.status_code),
        )

        logger.warning(
            BaseClientMessages.HTTP_ERROR.format(response.status_code, endpoint, error_message)
        )
        return RequestResult(success=False, detail=error_message, status_code=response.status_code)

    # --- ИЗМЕНЕНИЕ: Добавлены attempt и retry_count в сигнатуру ---
    def _handle_server_error(
        self, response: httpx.Response, endpoint: str, attempt: int, retry_count: int
    ) -> RequestResult:
        """Обрабатывает серверные ошибки (5xx)."""
        # --- ИЗМЕНЕНИЕ: Используем реальные значения для логирования ---
        logger.warning(
            BaseClientMessages.SERVER_ERROR_RETRY.format(
                response.status_code, attempt + 1, retry_count
            )
        )
        return RequestResult(
            success=False,
            detail=BaseClientMessages.SERVER_ERROR.format(response.status_code),
            status_code=response.status_code,
        )

    def _should_retry(self, status_code: int, attempt: int, retry_count: int) -> bool:
        """Определяет, нужно ли повторять запрос."""
        return status_code >= 500 and attempt < retry_count - 1

    def _calculate_backoff_delay(self, attempt: int, status_code: int) -> float:
        """Вычисляет задержку для backoff с jitter."""
        # Для серверных ошибок увеличиваем задержку
        if status_code >= 500:
            base_delay = min(2**attempt, 10.0)  # Сократили максимум для лучшей отзывчивости
        else:
            base_delay = min(2**attempt, 5.0)
        jitter = self.rng.uniform(0, 0.1 * base_delay)
        return base_delay + jitter
