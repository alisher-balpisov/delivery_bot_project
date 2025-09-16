from backend.src.auth.user_auth import get_current_user
from backend.src.core.database import get_db
from backend.src.core.logging import get_logger
from backend.src.schemas.user import UserCreateWithoutPassword, UserRead
from backend.src.users import service
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter()


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
