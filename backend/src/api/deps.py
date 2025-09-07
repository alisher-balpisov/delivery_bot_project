from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import verify_token
from src.common.enums import UserRole
from src.core.database import get_db
from src.core.logging import get_logger
from src.models.user import User
from src.users.service import get_user_by_telegram_id

security = HTTPBearer()

logger = get_logger(__name__)


async def get_current_user(
    token_data=Depends(security), db: AsyncSession = Depends(get_db)
) -> User:
    """Получить текущего пользователя по JWT токену"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = token_data.credentials
    token_data = verify_token(token)
    if token_data is None or token_data.telegram_id is None:
        raise credentials_exception

    user = await get_user_by_telegram_id(db, token_data.telegram_id)
    if user is None:
        raise credentials_exception
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


async def get_current_user_telegram_id(
    telegram_id: int, db: AsyncSession = Depends(get_db)
) -> User:
    """
    Получить текущего пользователя по telegram_id для простого авторизации.
    Используется вместо JWT зависимостей, как в описании.
    """
    logger.info(f"DEBUG: Вызван get_current_user_telegram_id с telegram_id={telegram_id}")
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        logger.warning(f"DEBUG: Пользователь с telegram_id={telegram_id} не найден")
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    logger.info(f"DEBUG: Найден пользователь {user.id} с telegram_id={telegram_id}")
    return user


async def get_current_shop_telegram(
    order_data: dict,  # Изменено для извлечения из тела
    db: AsyncSession = Depends(get_db),
) -> User:
    """Проверить, что пользователь - магазин по telegram_id из тела запроса"""
    telegram_id = order_data.get("telegram_id")
    if not telegram_id:
        logger.error("DEBUG: telegram_id не найден в теле запроса")
        raise HTTPException(status_code=400, detail="telegram_id required")

    logger.info(f"DEBUG: Вызван get_current_shop_telegram с telegram_id={telegram_id}")
    user = await get_current_user_telegram_id(telegram_id, db)
    if user.role != UserRole.shop:
        logger.warning(f"DEBUG: Пользователь {user.id} не имеет роли shop, роль={user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Shop role required."
        )
    logger.info(f"DEBUG: Подтвержден магазин {user.id} с telegram_id={telegram_id}")
    return user


# Также исправим get_current_user_telegram_id для совместимости
async def get_current_user_telegram_from_body(
    order_data: dict, db: AsyncSession = Depends(get_db)
) -> User:
    """Получить пользователя из тела запроса по telegram_id"""
    telegram_id = order_data.get("telegram_id")
    if not telegram_id:
        logger.error(
            "DEBUG: telegram_id не найден в теле запроса для get_current_user_telegram_from_body"
        )
        raise HTTPException(status_code=400, detail="telegram_id required")
    return await get_current_user_telegram_id(telegram_id, db)
