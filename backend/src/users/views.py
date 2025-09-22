from backend.src.auth.dependencies import RequireAllRoles
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.schemas.user import UserCreateWithoutPassword, UserRead, UserUpdate
from backend.src.users import service
from fastapi import APIRouter, HTTPException

logger = get_logger(__name__)

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_user_profile(
    current_user: RequireAllRoles,
):
    """
    Получение профиля текущего пользователя (идентифицированного по JWT).
    """
    logger.debug(f"Пользователь {current_user.id} запросил свой профиль.")
    return current_user


@router.put("/me", response_model=UserRead)
async def update_user_profile(
    user_data: UserUpdate,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Обновление профиля текущего пользователя.
    """
    logger.info(f"Обновление профиля для пользователя ID: {current_user.id}")
    updated_user = await service.update_user(db=db, user_id=current_user.id, user_data=user_data)
    if not updated_user:
        # Этот случай должен быть редким, так как get_current_user уже проверяет пользователя
        logger.error(
            f"Не удалось найти пользователя {current_user.id} для обновления, хотя он прошел аутентификацию."
        )
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    logger.info(f"Профиль для пользователя ID: {current_user.id} успешно обновлен.")
    return updated_user


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
