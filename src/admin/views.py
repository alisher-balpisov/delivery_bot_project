from fastapi import APIRouter, Depends, HTTPException
from src.admin import service
from src.core.config import is_admin
from src.core.logging import get_logger
from src.schemas.admin import AdminVerificationRequest, OneTimeCodeCreate, OneTimeCodeRead

logger = get_logger(__name__)

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
        logger.warning(f"❌ Unauthorized admin access attempt by ID: {admin_data.telegram_id}")
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Admin access required."
        )

    logger.info(f"✅ Admin verification successful for user: {admin_data.telegram_id}")
    return admin_data.telegram_id


@router.post("/generate-code", response_model=OneTimeCodeRead, status_code=201)
async def generate_one_time_code(
    admin_data: AdminVerificationRequest,
    code_data: OneTimeCodeCreate,
    admin_id: int = Depends(require_admin_verification),
):
    """
    Генерирует одноразовый код для регистрации пользователя с определенной ролью.
    Только для администраторов.

    Требует верификации администратора через AdminVerificationRequest в теле запроса.
    """
    try:
        logger.info(f"🚀 Generating OTC by admin {admin_id} for user {code_data.telegram_id}")

        new_code = await service.generate_one_time_code(
            telegram_id=code_data.telegram_id, user_role=code_data.user_role
        )

        logger.info(f"✅ OTC generated successfully for user {code_data.telegram_id}")
        return new_code

    except Exception as e:
        logger.error(f"❌ Failed to generate OTC: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate code")


@router.get("/verify-code/{code}", response_model=OneTimeCodeRead)
async def verify_one_time_code(code: str):
    """
    Проверяет одноразовый код.

    Код должен быть 6-значным числом и существовать в Redis.
    После успешной проверки код маркируется как использованный.
    """
    # Basic validation
    if not code.isdigit() or len(code) != 6:
        logger.warning(f"❌ Invalid code format: '{code}'")
        raise HTTPException(status_code=400, detail="Invalid code format. Must be 6 digits.")

    try:
        logger.info(f"🔍 Verifying code: {code}")

        verified_code = await service.verify_one_time_code(code=code)

        if not verified_code:
            logger.warning(f"❌ Code verification failed: {code}")
            raise HTTPException(status_code=404, detail="Invalid or expired code")

        logger.info(f"✅ Code verified successfully: {code}")
        return verified_code

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error during code verification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
