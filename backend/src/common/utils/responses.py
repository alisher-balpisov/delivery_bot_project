"""
Утилиты для формирования стандартизированных HTTP ответов.

Этот модуль предоставляет фабричные функции для создания
унифицированных ответов API.
"""

from typing import Any, TypeVar

from fastapi import status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


# ==============================================================================
# Стандартные сообщения
# ==============================================================================


class HTTPStatusMessages:
    """Стандартные сообщения для HTTP статусов."""

    # 2xx Success
    OK = "Операция выполнена успешно"
    CREATED = "Ресурс создан успешно"
    ACCEPTED = "Запрос принят в обработку"
    NO_CONTENT = "Нет контента для отображения"

    # 4xx Client Errors
    BAD_REQUEST = "Некорректный запрос"
    UNAUTHORIZED = "Требуется аутентификация"
    FORBIDDEN = "Доступ запрещен"
    NOT_FOUND = "Ресурс не найден"
    CONFLICT = "Конфликт данных"
    VALIDATION_ERROR = "Ошибка валидации данных"
    TOO_MANY_REQUESTS = "Превышен лимит запросов"

    # 5xx Server Errors
    INTERNAL_ERROR = "Внутренняя ошибка сервера"
    SERVICE_UNAVAILABLE = "Сервис временно недоступен"


# ==============================================================================
# Модели ответов
# ==============================================================================


class SuccessResponse(BaseModel):
    """Модель успешного ответа."""

    success: bool = True
    message: str
    data: Any = None


class ErrorResponse(BaseModel):
    """Модель ответа с ошибкой."""

    success: bool = False
    error: str
    detail: str
    timestamp: str | None = None


# ==============================================================================
# Фабрики успешных ответов
# ==============================================================================


def success_response(
    data: Any = None,
    message: str = HTTPStatusMessages.OK,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """
    Создает стандартный успешный ответ.

    Args:
        data: Данные для возврата
        message: Сообщение об успехе
        status_code: HTTP статус код

    Returns:
        JSONResponse с успешным ответом
    """
    content = {"success": True, "message": message}
    if data is not None:
        content["data"] = data
    return JSONResponse(content=content, status_code=status_code)


def created_response(data: Any = None, message: str = HTTPStatusMessages.CREATED) -> JSONResponse:
    """
    Создает ответ для созданного ресурса (201).

    Args:
        data: Данные созданного ресурса
        message: Сообщение об успехе

    Returns:
        JSONResponse со статусом 201
    """
    return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED)


def accepted_response(message: str = HTTPStatusMessages.ACCEPTED) -> JSONResponse:
    """
    Создает ответ о принятии запроса (202).

    Args:
        message: Сообщение о принятии

    Returns:
        JSONResponse со статусом 202
    """
    return success_response(message=message, status_code=status.HTTP_202_ACCEPTED)


def no_content_response() -> JSONResponse:
    """
    Создает ответ без контента (204).

    Returns:
        JSONResponse со статусом 204
    """
    return JSONResponse(content=None, status_code=status.HTTP_204_NO_CONTENT)


# ==============================================================================
# Фабрики ответов с ошибками
# ==============================================================================


def error_response(
    error: str,
    detail: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    timestamp: str | None = None,
) -> JSONResponse:
    """
    Создает стандартный ответ с ошибкой.

    Args:
        error: Тип ошибки
        detail: Детальное описание ошибки
        status_code: HTTP статус код
        timestamp: Временная метка (опционально)

    Returns:
        JSONResponse с ошибкой
    """
    content = {"success": False, "error": error, "detail": detail}
    if timestamp:
        content["timestamp"] = timestamp
    return JSONResponse(content=content, status_code=status_code)


def bad_request_response(detail: str = HTTPStatusMessages.BAD_REQUEST) -> JSONResponse:
    """
    Создает ответ о некорректном запросе (400).

    Args:
        detail: Детали ошибки

    Returns:
        JSONResponse со статусом 400
    """
    return error_response(
        error="BadRequest", detail=detail, status_code=status.HTTP_400_BAD_REQUEST
    )


def unauthorized_response(detail: str = HTTPStatusMessages.UNAUTHORIZED) -> JSONResponse:
    """
    Создает ответ о необходимости аутентификации (401).

    Args:
        detail: Детали ошибки

    Returns:
        JSONResponse со статусом 401
    """
    return error_response(
        error="Unauthorized", detail=detail, status_code=status.HTTP_401_UNAUTHORIZED
    )


def forbidden_response(detail: str = HTTPStatusMessages.FORBIDDEN) -> JSONResponse:
    """
    Создает ответ о запрете доступа (403).

    Args:
        detail: Детали ошибки

    Returns:
        JSONResponse со статусом 403
    """
    return error_response(error="Forbidden", detail=detail, status_code=status.HTTP_403_FORBIDDEN)


def not_found_response(detail: str = HTTPStatusMessages.NOT_FOUND) -> JSONResponse:
    """
    Создает ответ о ненайденном ресурсе (404).

    Args:
        detail: Детали ошибки

    Returns:
        JSONResponse со статусом 404
    """
    return error_response(error="NotFound", detail=detail, status_code=status.HTTP_404_NOT_FOUND)


def conflict_response(detail: str = HTTPStatusMessages.CONFLICT) -> JSONResponse:
    """
    Создает ответ о конфликте данных (409).

    Args:
        detail: Детали ошибки

    Returns:
        JSONResponse со статусом 409
    """
    return error_response(error="Conflict", detail=detail, status_code=status.HTTP_409_CONFLICT)


def validation_error_response(
    detail: str = HTTPStatusMessages.VALIDATION_ERROR,
) -> JSONResponse:
    """
    Создает ответ об ошибке валидации (422).

    Args:
        detail: Детали ошибки

    Returns:
        JSONResponse со статусом 422
    """
    return error_response(
        error="ValidationError",
        detail=detail,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def rate_limit_response(
    detail: str = HTTPStatusMessages.TOO_MANY_REQUESTS,
) -> JSONResponse:
    """
    Создает ответ о превышении лимита запросов (429).

    Args:
        detail: Детали ошибки

    Returns:
        JSONResponse со статусом 429
    """
    return error_response(
        error="RateLimitExceeded", detail=detail, status_code=status.HTTP_429_TOO_MANY_REQUESTS
    )


def internal_error_response(
    detail: str = HTTPStatusMessages.INTERNAL_ERROR,
) -> JSONResponse:
    """
    Создает ответ о внутренней ошибке сервера (500).

    Args:
        detail: Детали ошибки

    Returns:
        JSONResponse со статусом 500
    """
    return error_response(
        error="InternalServerError",
        detail=detail,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


__all__ = [
    "ErrorResponse",
    "HTTPStatusMessages",
    "SuccessResponse",
    "accepted_response",
    "bad_request_response",
    "conflict_response",
    "created_response",
    "error_response",
    "forbidden_response",
    "internal_error_response",
    "no_content_response",
    "not_found_response",
    "rate_limit_response",
    "success_response",
    "unauthorized_response",
    "validation_error_response",
]
