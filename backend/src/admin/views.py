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
    role: str, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)
):
    """
    Генерирует одноразовый код для регистрации пользователя определенной роли.
    Доступно только администраторам.

    Args:
        role: роли курьера или магазина ('courier' или 'shop')
    """
    # Проверяем, что role допустимая
    if role not in ["courier", "shop"]:
        raise HTTPException(
            status_code=400, detail="Недопустимая роль. Используйте 'courier' или 'shop'"
        )

    user_role = UserRole.courier if role == "courier" else UserRole.shop

    logger.info(f"Admin {current_user.telegram_id} generating {role} registration code")
    try:
        new_code = await admin_service.generate_registration_code(db=db, role=user_role)
        logger.info(f"{role.capitalize()} registration code generated successfully")
        return new_code
    except Exception as e:
        logger.error(f"Failed to generate {role} code: {e}")
        raise HTTPException(
            status_code=500, detail=f"Не удалось сгенерировать код для {role}: {e!s}"
        )


@router.get("/registration-codes", response_model=list[RegistrationCodeResponse])
async def get_all_registration_codes(
    current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)
):
    """
    Получить все коды регистрации (для администраторов).
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
    role: UserRole, current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)
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
    current_user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)
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
