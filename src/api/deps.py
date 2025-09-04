from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.models.user import User
from src.users.service import get_user_by_telegram_id

from common.enums import UserRole


async def get_current_user(telegram_id: int, db: AsyncSession = Depends(get_db)) -> User:
    """Получить текущего пользователя по Telegram ID"""
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def get_current_shop(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> User:
    """Проверить, что пользователь - магазин"""
    if current_user.role != UserRole.shop:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Shop role required."
        )
    return current_user
