from backend.src.auth import exceptions
from backend.src.core.logging import get_logger
from fastapi import APIRouter, HTTPException, status

router = APIRouter()

logger = get_logger(__name__)


def handle_invalid_credentials(e: exceptions.InvalidCredentialsError, telegram_id: int) -> None:
    """
    Логирует и выбрасывает HTTP исключение для неверных учетных данных.

    Args:
        e: Исключение с деталями ошибки
        telegram_id: Telegram ID пользователя для логирования

    Raises:
        HTTPException: HTTP 400 или 401 ошибка
    """
    logger.warning(f"Неверные учетные данные для telegram_id={telegram_id}: {e.detail}")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.detail)


def handle_account_locked(e: exceptions.AccountLockedError, telegram_id: int) -> None:
    """
    Логирует и выбрасывает HTTP исключение для заблокированного аккаунта.

    Args:
        e: Исключение с деталями ошибки
        telegram_id: Telegram ID пользователя для логирования

    Raises:
        HTTPException: HTTP 423 ошибка
    """
    logger.warning(
        f"Попытка доступа к заблокированному аккаунту telegram_id={telegram_id}: {e.detail}"
    )
    raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=e.detail)


def handle_attempts_exceeded(e: exceptions.AttemptsLimitExceededError, telegram_id: int) -> None:
    """
    Логирует и выбрасывает HTTP исключение при превышении лимита попыток.

    Args:
        e: Исключение с деталями ошибки
        telegram_id: Telegram ID пользователя для логирования

    Raises:
        HTTPException: HTTP 423 ошибка
    """
    logger.warning(f"Превышен лимит попыток для telegram_id={telegram_id}: {e.detail}")
    raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=e.detail)


def handle_generic_auth_error(e: exceptions.AuthError, telegram_id: int) -> None:
    """
    Логирует и выбрасывает HTTP исключение для общих ошибок аутентификации.

    Args:
        e: Исключение с деталями ошибки
        telegram_id: Telegram ID пользователя для логирования

    Raises:
        HTTPException: HTTP 401 ошибка
    """
    logger.warning(f"Ошибка аутентификации для telegram_id={telegram_id}: {e.detail}")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)


def handle_unexpected_error(telegram_id: int, operation: str) -> None:
    """
    Логирует непредвиденную ошибку и выбрасывает общее HTTP исключение.

    Args:
        telegram_id: Telegram ID пользователя для логирования
        operation: Название операции, при которой произошла ошибка

    Raises:
        HTTPException: HTTP 500 ошибка
    """
    logger.error(
        f"Непредвиденная ошибка в {operation} для telegram_id={telegram_id}",
        exc_info=True,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Внутренняя ошибка сервера",
    )
