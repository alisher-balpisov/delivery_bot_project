from collections.abc import Callable

from backend.src.common.enums import UserRole
from backend.src.core.config import settings
from backend.src.core.database import get_db
from backend.src.core.logging import get_logger
from backend.src.models.user import User
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

ACCOUNT_INACTIVE_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Аккаунт отключен",
)

ACCOUNT_BLOCKED_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Аккаунт заблокирован",
)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """
    Декодирует JWT токен, извлекает ID пользователя и возвращает активный объект User из БД.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key.get_secret_value(),
            algorithms=[settings.jwt.algorithm],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            logger.warning("Token payload is missing 'sub' (user_id)")
            raise CREDENTIALS_EXCEPTION
    except (JWTError, ValueError) as e:
        logger.warning(f"JWT decoding/validation error: {e}")
        raise CREDENTIALS_EXCEPTION

    user = await db.get(User, int(user_id))
    if user is None:
        logger.warning(f"User with id {user_id} from token not found in DB")
        raise CREDENTIALS_EXCEPTION

    if not user.is_active:
        logger.warning(f"Inactive user {user.id} attempted access")
        raise ACCOUNT_INACTIVE_EXCEPTION

    if user.is_blocked:
        logger.warning(f"Blocked user {user.id} attempted access")
        raise ACCOUNT_BLOCKED_EXCEPTION

    logger.debug(
        f"User {user.id} (tg: {user.telegram_id}) authenticated via JWT, role: {user.role.value}"
    )
    return user


def require_role(required_role: UserRole) -> Callable[[User], User]:
    """
    Зависимость для проверки роли пользователя.
    Работает поверх get_current_user.
    """

    async def role_dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role:
            logger.warning(
                f"Access denied for user {user.id} (tg: {user.telegram_id}): "
                f"role {user.role.value} is not {required_role.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав доступа",
            )
        logger.info(
            f"Role check passed: user {user.telegram_id} has required role {required_role.value}"
        )
        return user

    return role_dependency
