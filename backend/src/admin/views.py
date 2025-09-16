from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.admin import service as admin_service
from backend.src.auth.user_auth import require_role
from backend.src.common.enums import UserRole
from backend.src.core.database import get_db
from backend.src.schemas.admin import RegistrationCodeResponse

logger = getLogger(__name__)


router = APIRouter()


@router.post("/create-code/{role}", response_model=RegistrationCodeResponse, status_code=201)
async def create_registration_code(
    role: UserRole,
    current_user=Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Генерирует одноразовый код для регистрации пользователя определенной роли.
    Доступно только администраторам.

    Args:
        role: роли курьера или магазина ('courier' или 'shop')
    """
    # Проверяем, что role допустимая
    if role not in [UserRole.SHOP, UserRole.COURIER]:
        raise HTTPException(
            status_code=400, detail="Недопустимая роль. Используйте 'courier' или 'shop'"
        )

    logger.info(f"Admin {current_user.telegram_id} generating {role.value} registration code")
    try:
        new_code = await admin_service.generate_registration_code(db=db, role=role)
        logger.info(f"{role.capitalize()} registration code generated successfully")
        return new_code
    except Exception as e:
        logger.error(f"Failed to generate {role.value} code: {e}")
        raise HTTPException(
            status_code=500, detail=f"Не удалось сгенерировать код для {role.value}: {e!s}"
        )


# Temporary endpoint for initial setup - remove after first admin is registered
@router.post("/setup-code/{role}", response_model=RegistrationCodeResponse, status_code=201)
async def create_initial_registration_code(role: UserRole, db: AsyncSession = Depends(get_db)):
    """
    Temporary endpoint for creating registration codes during initial setup.
    Allows creating codes without authentication. Remove after first admin registration.
    """
    # Check that role is valid
    if role not in [UserRole.ADMIN, UserRole.SHOP, UserRole.COURIER]:
        raise HTTPException(
            status_code=400, detail="Invalid role. Use 'courier', 'shop', or 'admin'"
        )

    logger.info(f"Creating initial {role.value} registration code (temporary endpoint)")

    try:
        new_code = await admin_service.generate_registration_code(db=db, role=role)
        logger.info(f"Initial {role} registration code created successfully")
        return new_code
    except Exception as e:
        logger.error(f"Failed to create initial {role} code: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate code for {role}: {e!s}")


@router.get("/registration-codes", response_model=list[RegistrationCodeResponse])
async def get_all_registration_codes(
    current_user=Depends(require_role(UserRole.ADMIN)), db: AsyncSession = Depends(get_db)
):
    """
    Получить все коды регистрации.
    Доступно только администраторам.
    """
    logger.info(f"Admin {current_user.telegram_id} requesting all registration codes")
    try:
        codes = await admin_service.get_all_registration_codes(db=db)
        return codes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить коды: {e!s}")


@router.get("/registration-codes/{role}", response_model=list[RegistrationCodeResponse])
async def get_registration_codes_by_role(
    role: UserRole,
    current_user=Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить все коды регистрации для определенной роли.
    Доступно только администраторам.
    """
    logger.info(f"Admin {current_user.telegram_id} requesting registration codes for role {role}")
    try:
        codes = await admin_service.get_registration_codes_by_role(db=db, role=role)
        return codes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить коды: {e!s}")


@router.get("/registration-codes/stats", response_model=dict)
async def get_registration_codes_stats(
    current_user=Depends(require_role(UserRole.ADMIN)), db: AsyncSession = Depends(get_db)
):
    """
    Получить статистику кодов регистрации.
    Доступно только администраторам.
    """
    logger.info(f"Admin {current_user.telegram_id} requesting registration codes stats")
    try:
        stats = await admin_service.get_unused_registration_codes_count(db=db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить статистику: {e!s}")


@router.get("/system-stats", response_model=dict)
async def get_system_stats(
    current_user=Depends(require_role(UserRole.ADMIN)), db: AsyncSession = Depends(get_db)
):
    """
    Получить системную статистику (общие метрики пользователей, заказов, споров).
    Доступно только администраторам.
    """
    logger.info(f"Admin {current_user.telegram_id} requesting system stats")
    try:
        stats = await admin_service.get_system_stats(db=db)
        return stats
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(status_code=500, detail=f"Не удалось получить статистику: {e!s}")
