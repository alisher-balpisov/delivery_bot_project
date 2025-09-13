from backend.src.auth.user_auth import get_current_user
from backend.src.core.database import get_db
from backend.src.core.logging import get_logger
from backend.src.schemas.admin import CodeActivationRequest
from backend.src.schemas.user import UserCreateWithoutPassword, UserRead
from backend.src.users import service
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class ActivationResponse(BaseModel):
    user_id: int
    telegram_id: int
    role: str
    is_registered: bool


router = APIRouter()


@router.post("/register", response_model=ActivationResponse)
async def register_user(activation_data: CodeActivationRequest, db: AsyncSession = Depends(get_db)):
    """
    Регистрация нового пользователя через одноразовый код приглашения.
    Совпадает с описанием: привязывает telegram_id к роли через invite_code.
    Этот эндпоинт доступен без аутентификации для первоначальной регистрации.
    """
    logger.debug(f"Received activation data: {activation_data.model_dump()}")
    logger.info(
        f"User registration attempt: telegram_id={activation_data.telegram_id}, role={activation_data.role}"
    )

    try:
        response = await service.activate_code(
            db=db,
            telegram_id=activation_data.telegram_id,
            code=activation_data.code,
            requested_role=activation_data.role,
        )
        if response.success:
            logger.info(f"User registration successful: telegram_id={activation_data.telegram_id}")
            return ActivationResponse(
                user_id=response.user_id,
                telegram_id=activation_data.telegram_id,
                role=response.role,
                is_registered=True,
            )
        else:
            logger.warning(
                f"User registration failed: telegram_id={activation_data.telegram_id}, detail={response.detail}"
            )
            raise ValueError(response.detail or "Ошибка регистрации")
    except ValueError as e:
        logger.warning(f"User registration failed: {e!s}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserRead)
async def get_user_profile(
    current_user: UserRead = Depends(get_current_user),
):
    """
    Получение профиля текущего пользователя.
    """
    return current_user


@router.post("/complete-registration", response_model=UserRead)
async def complete_user_registration(
    user_data: UserCreateWithoutPassword,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Завершение регистрации текущего пользователя.
    """
    logger.info(f"Complete registration attempt for user: {current_user.telegram_id}")

    try:
        user = await service.complete_user_registration(
            db=db, telegram_id=current_user.telegram_id, user_data=user_data
        )
        logger.info(f"Registration completed successfully for user: {current_user.telegram_id}")
        return user
    except ValueError as e:
        logger.warning(f"Registration completion failed for user {current_user.telegram_id}: {e!s}")
        raise HTTPException(status_code=400, detail=str(e))
