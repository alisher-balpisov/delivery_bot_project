from backend.src.auth.dependencies import get_current_user
from backend.src.core.database import get_db
from backend.src.core.logging import get_logger
from backend.src.models.user import User
from backend.src.schemas.user import UserCreateWithoutPassword, UserRead, UserUpdate
from backend.src.users import service
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Получение профиля текущего пользователя (идентифицированного по JWT).
    """
    return current_user


@router.put("/me", response_model=UserRead)
async def update_user_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновление профиля текущего пользователя.
    """
    logger.info(f"Updating profile for user ID: {current_user.id}")
    updated_user = await service.update_user(db=db, user_id=current_user.id, user_data=user_data)
    if not updated_user:
        # This case should be rare as get_current_user already validates the user
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user


@router.post("/complete-registration", response_model=UserRead)
async def complete_user_registration(
    user_data: UserCreateWithoutPassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Завершение регистрации текущего пользователя (идентифицированного по JWT).
    """
    logger.info(f"Complete registration attempt for user ID: {current_user.id}")

    try:
        user = await service.complete_user_registration(
            db=db, user_id=current_user.id, user_data=user_data
        )
        logger.info(f"Registration completed successfully for user ID: {current_user.id}")
        return user
    except ValueError as e:
        logger.warning(f"Registration completion failed for user ID {current_user.id}: {e!s}")
        raise HTTPException(status_code=400, detail=str(e))
