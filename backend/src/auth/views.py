from backend.src.auth import exceptions, service
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.schemas.auth import AuthByCodeRequest, AuthSuccessResponse
from fastapi import APIRouter, HTTPException, status

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
    logger.info(f"Попытка аутентификации по коду для telegram_id: {form_data.telegram_id}")
    try:
        result = await service.AuthService.auth_by_code(
            db=db,
            telegram_id=form_data.telegram_id,
            username=form_data.username,
            code=form_data.code,
        )
        logger.info(f"Успешная аутентификация для telegram_id: {form_data.telegram_id}")
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
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в auth_by_code: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера"
        )
