from logging import getLogger

from backend.src.common.enums import UserRole
from backend.src.core.database import get_db
from backend.src.models.user import User
from backend.src.users.service import get_user_by_telegram_id
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = getLogger(__name__)


async def get_current_user(
    x_telegram_id: int | None = Header(None, alias="X-Telegram-ID"),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if x_telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="X-Telegram-ID header is required"
        )

    user = await get_user_by_telegram_id(db, x_telegram_id)
    if user is None:
        logger.warning(f"User not found by telegram_id {x_telegram_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )

    # Проверка активации пользователя
    if not user.is_active:
        logger.warning(f"Inactive user {x_telegram_id} attempted access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт отключен",
        )

    if user.is_blocked:
        logger.warning(f"Blocked user {x_telegram_id} attempted access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )

    logger.info(f"User {x_telegram_id} authenticated, role: {user.role.value}")
    return user


def require_role(required_role: UserRole) -> User | None:
    """
    Декоратор для проверки роли пользователя.

    Args:
        required_role: Требуемая роль ('admin', 'shop', 'courier')

    Returns:
        Зависимость FastAPI
    """

    async def role_dependency(user=Depends(get_current_user)):
        if user.role != required_role:
            logger.warning(
                f"Access denied: user {user.telegram_id} has role {user.role.value}, "
                f"required {required_role}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав доступа"
            )

        logger.info(f"Role check passed: user {user.telegram_id} has required role {required_role}")
        return user

    return role_dependency
