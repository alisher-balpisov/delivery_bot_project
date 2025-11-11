from backend.src.common.enums import TokenType
from backend.src.core.database import DbSession, settings
from backend.src.core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from icecream import ic

from . import exceptions, service
from .auth_error_handlers import *
from .schemas import (
    AuthByCodeRequest,
    AuthSuccessResponse,
    LoginRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
)

router = APIRouter()

logger = get_logger(__name__)


@router.post("/by-code", response_model=AuthSuccessResponse)
async def auth_by_code(
    form_data: AuthByCodeRequest,
    db: DbSession,
):
    """
    Регистрация или аутентификация пользователя по коду приглашения.

    Процесс:
    - Если пользователь новый: регистрирует его с указанной ролью из кода
    - Если пользователь существует: возвращает новые токены

    В обоих случаях возвращает JWT токены и информацию о пользователе.

    Args:
        form_data: Данные запроса с telegram_id, кодом и username
        db: Сессия базы данных

    Returns:
        Объект AuthSuccessResponse с токенами и информацией о пользователе

    Raises:
        HTTPException:
            - 400: Неверный код
            - 423: Превышен лимит попыток или аккаунт заблокирован
            - 401: Общая ошибка аутентификации
            - 500: Внутренняя ошибка сервера
    """
    logger.info(f"Попытка аутентификации по коду для telegram_id={form_data.telegram_id}")

    try:
        ic(form_data)
        result = await service.auth_by_code(
            db=db,
            telegram_id=form_data.telegram_id,
            username=form_data.username,
            code=form_data.code,
        )
        logger.info(
            f"Успешная аутентификация для telegram_id={form_data.telegram_id}, "
            f"already_registered={result.already_registered}"
        )
        return result

    except exceptions.InvalidCredentialsError as e:
        handle_invalid_credentials(e, form_data.telegram_id)
    except exceptions.AttemptsLimitExceededError as e:
        handle_attempts_exceeded(e, form_data.telegram_id)
    except exceptions.AccountLockedError as e:
        handle_account_locked(e, form_data.telegram_id)
    except exceptions.AuthError as e:
        handle_generic_auth_error(e, form_data.telegram_id)
    except Exception:
        handle_unexpected_error(form_data.telegram_id, "auth_by_code")


@router.post("/login", response_model=AuthSuccessResponse)
async def login(
    form_data: LoginRequest,
    db: DbSession,
):
    """
    Вход существующего зарегистрированного пользователя.

    Проверяет, что пользователь существует и завершил регистрацию,
    затем возвращает новые JWT токены.

    Args:
        form_data: Данные запроса с telegram_id
        db: Сессия базы данных

    Returns:
        Объект AuthSuccessResponse с токенами и информацией о пользователе

    Raises:
        HTTPException:
            - 401: Пользователь не найден
            - 403: Регистрация не завершена или аккаунт неактивен
            - 423: Аккаунт заблокирован
            - 500: Внутренняя ошибка сервера
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
    except exceptions.RegistrationIncompleteError as e:
        logger.warning(f"Пользователь telegram_id={form_data.telegram_id} не завершил регистрацию")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.detail)
    except exceptions.AccountInactiveError as e:
        logger.warning(f"Неактивный аккаунт для telegram_id={form_data.telegram_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.detail)
    except exceptions.AccountLockedError as e:
        handle_account_locked(e, form_data.telegram_id)
    except exceptions.AuthError as e:
        handle_generic_auth_error(e, form_data.telegram_id)
    except Exception:
        handle_unexpected_error(form_data.telegram_id, "login")


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: DbSession,
):
    """
    Обновление access токена с помощью refresh токена.

    Принимает валидный refresh токен и возвращает новую пару токенов
    (access + refresh).

    Args:
        request: Запрос с refresh токеном
        db: Сессия базы данных

    Returns:
        Объект RefreshTokenResponse с новыми токенами

    Raises:
        HTTPException:
            - 401: Refresh токен невалиден или истёк
            - 403: Проблемы с аккаунтом (заблокирован/неактивен)
            - 500: Внутренняя ошибка сервера
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
            token_type=TokenType.BEARER,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера",
        )


@router.post("/token", response_model=AuthSuccessResponse)
async def login_for_swagger(
    db: DbSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Эндпоинт для получения токена через Swagger UI.

    Использует стандартную форму OAuth2 Password Flow.
    Поле username интерпретируется как Telegram ID.
    Поле password игнорируется.

    Args:
        db: Сессия базы данных
        form_data: Форма OAuth2 с username (telegram_id) и password (игнорируется)

    Returns:
        Объект AuthSuccessResponse с токенами

    Raises:
        HTTPException:
            - 400: Username не является валидным числом
            - 401: Неверные учетные данные
            - 423: Аккаунт заблокирован
            - 500: Внутренняя ошибка сервера
    """
    logger.info(f"Попытка входа через /token для username={form_data.username}")

    try:
        telegram_id = int(form_data.username)
    except (ValueError, TypeError):
        logger.warning(f"Невалидный username (должен быть Telegram ID): {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поле username должно содержать числовой Telegram ID",
        )

    try:
        result = await service.login(db=db, telegram_id=telegram_id)
        logger.info(f"Успешный вход через /token для telegram_id={telegram_id}")
        return result

    except exceptions.InvalidCredentialsError as e:
        logger.warning(f"Неверные учетные данные для telegram_id={telegram_id}: {e.detail}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)
    except exceptions.RegistrationIncompleteError as e:
        logger.warning(f"Регистрация не завершена для telegram_id={telegram_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.detail)
    except exceptions.AccountLockedError as e:
        handle_account_locked(e, telegram_id)
    except Exception:
        handle_unexpected_error(telegram_id, "login_for_swagger")
