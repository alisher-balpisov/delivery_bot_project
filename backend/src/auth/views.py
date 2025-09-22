import redis.asyncio as aioredis
from backend.src.auth import exceptions, service
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.core.redis import get_redis
from backend.src.schemas.auth import AuthByCodeRequest, AuthSuccessResponse, Token, TokenRequest
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter()
logger = get_logger(__name__)


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: TokenRequest, db: DbSession) -> Token:
    """
    Выдает JWT токен для пользователя по его telegram_id.
    Если пользователь не найден, создает гостя.
    Используется ботом для получения токена перед каждым запросом к API.
    """
    logger.debug(f"Запрос токена для telegram_id: {form_data.telegram_id}")
    user = await service.get_user_by_telegram_id_or_create_guest(form_data.telegram_id, db)
    access_token = service.create_access_token(user)
    logger.debug(f"Выдан токен для пользователя {user.id} (telegram_id: {form_data.telegram_id})")
    return Token(access_token=access_token)


@router.post("/by-code", response_model=AuthSuccessResponse)
async def auth_by_code(
    form_data: AuthByCodeRequest,
    db: DbSession,
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Аутентификация по коду приглашения.
    - В случае успеха возвращает JWT токен и данные пользователя.
    - В случае, если пользователь уже был зарегистрирован, возвращает то же самое,
      но с флагом `already_registered: true`.
    """
    logger.info(f"Попытка аутентификации по коду для telegram_id: {form_data.telegram_id}")
    try:
        result = await service.auth_by_code(db, redis, form_data.telegram_id, form_data.code)
        logger.info(f"Успешная аутентификация для telegram_id: {form_data.telegram_id}")
        return result
    except exceptions.UserAlreadyRegisteredError as e:
        # Это не ошибка, а штатная ситуация. Возвращаем успешный ответ.
        logger.info(
            f"Пользователь {form_data.telegram_id} уже зарегистрирован. Возвращаем существующие данные."
        )
        return AuthSuccessResponse(
            user=e.user_data,
            access_token=e.access_token,
            already_registered=True,
        )
    except exceptions.InvalidCredentialsError as e:
        logger.warning(f"Неверный код для telegram_id={form_data.telegram_id}: {e.detail}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.detail)
    except (exceptions.AttemptsLimitExceededError, exceptions.ccountLockedError) as e:
        logger.warning(f"Блокировка аккаунта для telegram_id={form_data.telegram_id}: {e.detail}")
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=e.detail)
    except exceptions.AuthError as e:
        # Общий обработчик для других ошибок аутентификации
        logger.warning(
            f"Общая ошибка аутентификации для telegram_id={form_data.telegram_id}: {e.detail}"
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в auth_by_code: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера"
        )
