import logging

from backend.src.auth.user_auth import create_access_token
from backend.src.common.enums import UserRole
from backend.src.core.database import get_db
from backend.src.users.service import get_user_by_telegram_id
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

logger = logging.getLogger(__name__)


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    telegram_id: int


@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_user_by_telegram_id(db, telegram_id=form_data.telegram_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect telegram_id",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if user.role == UserRole.PENDING or user.role is None:
            logger.warning(f"User {user.telegram_id} has invalid role {user.role}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect telegram_id",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"User found: {user.telegram_id}, {user.role}, active: {user.is_active}")
        access_token = create_access_token(data={"sub": str(user.telegram_id)})
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Error in login_for_access_token: {e}", exc_info=True)
        raise


@router.post("/bot-login")
async def bot_login_for_access_token(form_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Специальный эндпоинт для авторизации через бота
    Возвращает дополнительные данные пользователя для упрощения логики в боте
    """
    try:
        user = await get_user_by_telegram_id(db, telegram_id=form_data.telegram_id)
        if not user:
            logger.warning(f"User not found: {form_data.telegram_id}")
            return {"success": False, "detail": "User not found"}

        # Проверка валидности роли пользователя (не pending)
        from backend.src.common.enums import UserRole

        if user.role == UserRole.PENDING or user.role is None:
            logger.warning(f"User {user.telegram_id} has invalid role {user.role}")
            return {"success": False, "detail": "User has invalid role"}

        logger.info(f"User found: {user.telegram_id}, {user.role}, active: {user.is_active}")
        access_token = create_access_token(data={"sub": str(user.telegram_id)})

        # Возвращаем дополнительные данные для бота
        return {
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "name": user.name,
                "role": user.role.value if user.role else None,
                "is_active": user.is_active,
                "is_blocked": user.is_blocked if hasattr(user, "is_blocked") else False,
            },
            "role": user.role.value if user.role else None,
        }
    except Exception as e:
        logger.error(f"Error in bot_login_for_access_token: {e}", exc_info=True)
        return None
