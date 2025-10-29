from fastapi import APIRouter, HTTPException

from backend.src.admin import service
from backend.src.auth.dependencies import RequireAdmin
from backend.src.common.enums import UserRole
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.schemas.admin import RegistrationCodeResponse

logger = get_logger(__name__)


router = APIRouter()


@router.post("/registration-codes", response_model=RegistrationCodeResponse, status_code=201)
async def create_registration_code(
    role: UserRole,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Генерирует одноразовый код для регистрации пользователя определенной роли.
    Доступно только администраторам.
    """
    logger.info(f"Администратор {current_user} инициировал генерацию кода для роли {role.value}")

    try:
        new_code = await service.create_registration_code(
            db=db, role=role, created_by_admin_id=current_user.id
        )

        logger.info(
            f"Код регистрации '{new_code.code}' для роли {role.value} успешно сгенерирован "
            f"администратором id={current_user}"
        )
        return new_code
    except RuntimeError as e:
        logger.error(
            f"Критическая ошибка при генерации кода для роли {role.value} "
            f"администратором {current_user}: {e}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при генерации кода.")


@router.get("/registration-codes", response_model=list[RegistrationCodeResponse])
async def get_all_registration_codes(current_user: RequireAdmin, db: DbSession):
    """
    Получить все коды регистрации.
    Доступно только администраторам.
    """
    logger.info(f"Администратор ID {current_user.id} запрашивает все коды регистрации")
    try:
        codes = await service.get_all_registration_codes(db=db)
        return codes
    except Exception as e:
        logger.error(f"Ошибка при получении всех кодов регистрации: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить коды: {e!s}")


@router.get("/registration-codes/{role}", response_model=list[RegistrationCodeResponse])
async def get_registration_codes_by_role(
    role: UserRole,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Получить все коды регистрации для определенной роли.
    Доступно только администраторам.
    """
    logger.info(
        f"Администратор ID {current_user.id} запрашивает коды регистрации для роли {role.value}"
    )
    try:
        codes = await service.get_registration_codes_by_role(db=db, role=role)
        return codes
    except Exception as e:
        logger.error(
            f"Ошибка при получении кодов регистрации для роли {role.value}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Не удалось получить коды: {e!s}")


@router.get("/registration-codes/stats", response_model=dict)
async def get_registration_codes_stats(current_user: RequireAdmin, db: DbSession):
    """
    Получить статистику кодов регистрации.
    Доступно только администраторам.
    """
    logger.info(f"Администратор ID {current_user.id} запрашивает статистику по кодам регистрации")
    try:
        stats = await service.get_unused_registration_codes_count(db=db)
        return stats
    except Exception as e:
        logger.error(f"Ошибка при получении статистики кодов регистрации: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить статистику: {e!s}")


@router.get("/system-stats", response_model=dict)
async def get_system_stats(current_user: RequireAdmin, db: DbSession):
    """
    Получить системную статистику (общие метрики пользователей, заказов, споров).
    Доступно только администраторам.
    """
    logger.info(f"Администратор ID {current_user.id} запрашивает системную статистику")
    try:
        stats = await service.get_system_stats(db=db)
        return stats
    except Exception as e:
        logger.error(f"Ошибка при получении системной статистики: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить статистику: {e!s}")
