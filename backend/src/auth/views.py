import redis.asyncio as aioredis
from backend.src.auth import service
from backend.src.auth.eceptions import (
    AccountLockedError,
    AttemptsLimitExceededError,
    AuthError,
    InvalidCredentialsError,
    UserAlreadyRegisteredError,
)
from backend.src.core.database import get_db
from backend.src.core.logging import get_logger
from backend.src.core.redis import get_redis
from backend.src.schemas.auth import AuthByCodeRequest, AuthSuccessResponse, Token, TokenRequest
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = get_logger(__name__)


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: TokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Выдает JWT токен для пользователя по его telegram_id.
    Если пользователь не найден, создает гостя.
    """
    user = await service.get_user_by_telegram_id_or_create_guest(form_data.telegram_id, db)
    access_token = service.create_access_token(user)
    return Token(access_token=access_token)


@router.post("/by-code", response_model=AuthSuccessResponse)
async def auth_by_code(
    form_data: AuthByCodeRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Аутентификация по коду приглашения.
    - В случае успеха возвращает JWT токен и данные пользователя.
    - В случае, если пользователь уже был зарегистрирован, возвращает то же самое,
      но с флагом `already_registered: true`.
    """
    try:
        result = await service.auth_by_code(db, redis, form_data.telegram_id, form_data.code)
        return result
    except UserAlreadyRegisteredError as e:
        # Это не ошибка, а штатная ситуация. Возвращаем успешный ответ.
        return AuthSuccessResponse(
            user=e.user_data,
            access_token=e.access_token,
            already_registered=True,
        )
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.detail)
    except (AttemptsLimitExceededError, AccountLockedError) as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=e.detail)
    except AuthError as e:
        # Общий обработчик для других ошибок аутентификации
        logger.warning(f"Generic auth error for telegram_id={form_data.telegram_id}: {e.detail}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error in auth_by_code_view: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера"
        )
