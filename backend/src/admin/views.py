from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.admin import service as admin_service
from src.auth.bot_auth import verify_bot_token
from src.common.enums import UserRole
from src.core.config import is_admin
from src.core.database import get_db
from src.schemas.registration_code import RegistrationCodeResponse


class AdminVerificationRequest(BaseModel):
    telegram_id: int

    class Config:
        from_attributes = True


class GenerateCodeRequest(BaseModel):
    role: UserRole
    admin_telegram_id: int

    class Config:
        from_attributes = True


router = APIRouter()


def require_admin_verification(admin_data: AdminVerificationRequest) -> int:
    """
    Зависимость для проверки прав администратора.

    Args:
        admin_data: Данные для верификации администратора

    Returns:
        telegram_id администратора если верификация успешна

    Raises:
        HTTPException: Если доступ запрещен
    """
    if not is_admin(admin_data.telegram_id):
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Admin access required."
        )

    return admin_data.telegram_id


@router.post(
    "/generate-registration-code", response_model=RegistrationCodeResponse, status_code=201
)
async def generate_registration_code(
    role: UserRole, db: AsyncSession = Depends(get_db), bot_token=Depends(verify_bot_token)
):
    """
    Генерирует одноразовый код для регистрации пользователя с определенной ролью.
    Защищено JWT токеном бота.
    """
    try:
        new_code = await admin_service.generate_registration_code(db=db, role=role)
        return new_code
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сгенерировать код: {e!s}")


@router.get("/registration-codes", response_model=list[RegistrationCodeResponse])
async def get_all_registration_codes(
    db: AsyncSession = Depends(get_db), bot_token=Depends(verify_bot_token)
):
    """
    Получить все коды регистрации (для администраторов).
    Защищено JWT токеном бота.
    """
    try:
        codes = await admin_service.get_all_registration_codes(db=db)
        return codes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить коды: {e!s}")


@router.get("/registration-codes/{role}", response_model=list[RegistrationCodeResponse])
async def get_registration_codes_by_role(
    role: UserRole, db: AsyncSession = Depends(get_db), bot_token=Depends(verify_bot_token)
):
    """
    Получить все коды регистрации для определенной роли.
    Защищено JWT токеном бота.
    """
    try:
        codes = await admin_service.get_registration_codes_by_role(db=db, role=role)
        return codes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить коды: {e!s}")


@router.get("/registration-codes/stats", response_model=dict)
async def get_registration_codes_stats(
    db: AsyncSession = Depends(get_db), bot_token=Depends(verify_bot_token)
):
    """
    Получить статистику кодов регистрации.
    Защищено JWT токеном бота.
    """
    try:
        stats = await admin_service.get_unused_registration_codes_count(db=db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить статистику: {e!s}")
