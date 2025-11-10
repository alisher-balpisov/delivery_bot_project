from backend.src.auth.dependencies import RequireAllRoles, RequireShopOrCourier
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.users import service
from backend.src.users.schemas import UserBase, UserCreateWithoutPassword, UserRead, UserUpdate
from fastapi import APIRouter, HTTPException

logger = get_logger(__name__)

router = APIRouter()


@router.get("/me", response_model=UserBase)
async def get_my_profile(
    current_user: RequireAllRoles,
):
    """
    Получение профиля текущего пользователя (идентифицированного по JWT).
    """
    logger.debug(f"Пользователь {current_user} запросил свой профиль.")
    return current_user


@router.put("/me", response_model=UserBase)
async def update_my_profile(
    profile_data: UserUpdate,
    current_user: RequireShopOrCourier,
    db: DbSession,
):
    """
    Обновление профиля текущего пользователя (магазин или курьер).
    """
    logger.info(f"Обновление профиля для пользователя {current_user}")

    try:
        updated_user = await service.update_my_profile(
            db=db, user_id=current_user.id, profile_data=profile_data
        )
        logger.info(f"Профиль для пользователя {current_user} успешно обновлен.")
        return updated_user

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Профиль пользователя не найден или не может быть обновлен: {e!s}",
        )
    except Exception as e:
        logger.error(
            f"Непредвиденная ошибка при обновлении профиля для пользователя {current_user}: {e!s}",
            exc_info=True,
        )
        raise


@router.post("/complete-registration", response_model=UserRead)
async def complete_user_registration(
    user_data: UserCreateWithoutPassword,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Завершение регистрации текущего пользователя (идентифицированного по JWT).
    """
    logger.info(f"Попытка завершения регистрации для пользователя ID: {current_user.id}")

    try:
        user = await service.complete_user_registration(
            db=db, user_id=current_user.id, user_data=user_data
        )
        logger.info(f"Регистрация успешно завершена для пользователя ID: {current_user.id}")
        return user
    except ValueError as e:
        logger.warning(
            f"Ошибка завершения регистрации для пользователя ID {current_user.id}: {e!s}"
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Непредвиденная ошибка при завершении регистрации для пользователя ID {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
