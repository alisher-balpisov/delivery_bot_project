from backend.src.auth import exceptions
from backend.src.core.database import DbSession, settings
from backend.src.core.logging import get_logger
from backend.src.schemas.auth import (
    AuthByCodeRequest,
    AuthSuccessResponse,
    LoginRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from . import service

router = APIRouter()

logger = get_logger(__name__)


@router.post("/by-code", response_model=AuthSuccessResponse)
async def auth_by_code(
    form_data: AuthByCodeRequest,
    db: DbSession,
):
    """
    Аутентификация по коду приглашения.
    - В случае успеха возвращает JWT токен и данные пользователя.
    - В случае, если пользователь уже был зарегистрирован, возвращает то же самое,
      но с флагом `already_registered: true`.
    """
    logger.info(f"Попытка аутентификации по коду для telegram_id={form_data.telegram_id}")
    try:
        result = await service.auth_by_code(
            db=db,
            telegram_id=form_data.telegram_id,
            username=form_data.username,
            code=form_data.code,
        )
        logger.info(f"Успешная аутентификация для telegram_id={form_data.telegram_id}")
        return result

    except exceptions.InvalidCredentialsError as e:
        logger.warning(f"Неверный код для telegram_id={form_data.telegram_id}: {e.detail}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.detail)
    except (exceptions.AttemptsLimitExceededError, exceptions.AccountLockedError) as e:
        logger.warning(f"Блокировка аккаунта для telegram_id={form_data.telegram_id}: {e.detail}")
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=e.detail)
    except exceptions.AuthError as e:
        logger.warning(
            f"Общая ошибка аутентификации для telegram_id={form_data.telegram_id}: {e.detail}"
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)
    except Exception:
        logger.error(
            f"Непредвиденная ошибка в auth_by_code для telegram_id={form_data.telegram_id}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера"
        )


@router.post("/login", response_model=AuthSuccessResponse)
async def login(
    form_data: LoginRequest,
    db: DbSession,
):
    """
    Аутентификация (вход) существующего пользователя.
    - В случае успеха возвращает новый JWT токен и данные пользователя.
    """
    logger.info(f"Попытка входа для telegram_id={form_data.telegram_id}")
    try:
        result = await service.login(
            db=db,
            telegram_id=form_data.telegram_id,
        )
        logger.info(f"Успешный вход для telegram_id={form_data.telegram_id}")
        return result

    except exceptions.InvalidCredentialsError as e:
        logger.warning(f"Неудачный вход для telegram_id={form_data.telegram_id}: {e.detail}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)
    except exceptions.AccountLockedError as e:
        logger.warning(
            f"Блокировка аккаунта при входе для telegram_id={form_data.telegram_id}: {e.detail}"
        )
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=e.detail)
    except exceptions.RegistrationIncompleteError as e:
        logger.warning(
            f"Пользователь telegram_id={form_data.telegram_id} не завершил процесс регистрации."
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.detail)
    except exceptions.AuthError as e:
        logger.warning(
            f"Общая ошибка аутентификации при входе для telegram_id={form_data.telegram_id}: {e.detail}"
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)

    except Exception:
        logger.error(
            f"Непредвиденная ошибка в эндпоинте login для telegram_id={form_data.telegram_id}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: DbSession,
):
    """
    Обновление access токена с помощью refresh токена.

    - Получает валидный refresh token (JWT)
    - Проверяет его подлинность и срок действия
    - Возвращает новую пару токенов
    """
    logger.info("Запрос на обновление токена")

    try:
        new_access_token, new_refresh_token = await service.refresh_access_token(
            db=db,
            refresh_token=request.refresh_token,
        )

        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.jwt.access_token_expire_minutes * 60,
            refresh_expires_in=settings.jwt.refresh_token_expire_days * 24 * 60 * 60,
        )

    except exceptions.InvalidRefreshTokenError as e:
        logger.warning(f"Невалидный refresh token: {e.detail}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)

    except (exceptions.AccountLockedError, exceptions.AccountInactiveError) as e:
        logger.warning(f"Проблема с аккаунтом при обновлении токена: {e.detail}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.detail)

    except Exception:
        logger.error("Непредвиденная ошибка при обновлении токена", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера"
        )


@router.post("/token", response_model=AuthSuccessResponse)
async def login_for_swagger(db: DbSession, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Эндпоинт для получения токена через Swagger UI.
    Использует `username` как `telegram_id` и игнорирует `password`.
    """
    logger.info(f"Попытка входа через /token для username={form_data.username}")
    try:
        # Мы используем поле username формы для передачи telegram_id
        telegram_id = int(form_data.username)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поле username должно содержать числовой Telegram ID",
        )

    # Здесь мы просто вызываем уже написанную вами сервисную функцию login
    try:
        result = await service.login(db=db, telegram_id=telegram_id)
        # OAuth2PasswordRequestForm ожидает, что ответ будет содержать 'access_token'
        # Наша схема AuthSuccessResponse уже подходит
        return result
    except exceptions.InvalidCredentialsError as e:
        # Для password flow принято отдавать 401 ошибку
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)
    except exceptions.AccountLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=e.detail)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера"
        )
