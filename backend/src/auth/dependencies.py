from typing import Annotated

from backend.src.auth import exceptions
from backend.src.common.enums import UserRole
from backend.src.core.config import settings
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.user import User
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def _get_current_user(db: DbSession, token: str = Depends(oauth2_scheme)) -> User:
    """
    Декодирует JWT токен, извлекает ID пользователя и возвращает активный объект User из БД.

    Args:
        token: JWT токен доступа.
        db: Сессия базы данных.

    Returns:
        Объект пользователя, если аутентификация прошла успешно.

    Raises:
        CREDENTIALS_EXCEPTION: Если токен невалиден, отсутствует или пользователь не найден.
        ACCOUNT_INACTIVE_EXCEPTION: Если аккаунт пользователя неактивен.
        ACCOUNT_BLOCKED_EXCEPTION: Если аккаунт пользователя заблокирован.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key.get_secret_value(),
            algorithms=[settings.jwt.algorithm],
        )

        try:
            user_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            raise exceptions.CREDENTIALS_EXCEPTION

        if user_id is None:
            logger.warning("В токене отсутствует 'sub' (ID пользователя)")
            raise exceptions.CREDENTIALS_EXCEPTION

    except (JWTError, ValueError) as e:
        logger.warning(f"Ошибка декодирования/валидации JWT: {e}")
        raise exceptions.CREDENTIALS_EXCEPTION

    user = await db.get(User, user_id)
    if user is None:
        logger.warning(f"Пользователь с ID {user_id} из токена не найден в БД")
        raise exceptions.CREDENTIALS_EXCEPTION

    if user.is_deleted:
        logger.warning(f"Неактивный пользователь {user.id} попытался получить доступ")
        raise exceptions.ACCOUNT_INACTIVE_EXCEPTION

    if user.is_blocked:
        logger.warning(f"Заблокированный пользователь {user.id} попытался получить доступ")
        raise exceptions.ACCOUNT_BLOCKED_EXCEPTION

    logger.debug(
        f"Пользователь {user.id} (tg: {user.telegram_id}) аутентифицирован через JWT, роль: {user.role.value}"
    )
    return user


def _require_role(allowed_roles: UserRole | list[UserRole] | tuple[UserRole, ...]) -> User:
    """
    Зависимость для проверки роли пользователя.
    Работает поверх get_current_user.

    Args:
        allowed_roles: Требуемые роли пользователя.
    """
    if isinstance(allowed_roles, UserRole):
        allowed_roles = [allowed_roles]  # Оборачиваем одиночную роль в список

    async def _role_dependency(user: User = Depends(_get_current_user)) -> User:
        """Проверяет, соответствует ли роль пользователя требуемой."""
        if user.role not in allowed_roles:
            logger.warning(
                f"Доступ запрещен для пользователя {user.id} (tg: {user.telegram_id}): "
                f"роль {user.role.value} не соответствует требуемым {[role.value for role in allowed_roles]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Недостаточно прав доступа. Требуется одна из ролей: {[role.value for role in allowed_roles]}",
            )

        logger.debug(
            f"Проверка роли пройдена: пользователь {user.telegram_id} имеет необходимую роль"
        )
        return user

    return _role_dependency


# Зависимости для конкретных ролей
RequireAdmin = Annotated[User, Depends(_require_role(UserRole.ADMIN))]
RequireShop = Annotated[User, Depends(_require_role(UserRole.SHOP))]
RequireCourier = Annotated[User, Depends(_require_role(UserRole.COURIER))]

# Зависимость для группы ролей (название можно уточнить)
RequireShopOrCourier = Annotated[User, Depends(_require_role([UserRole.SHOP, UserRole.COURIER]))]
RequireAllRoles = Annotated[
    User,
    Depends(
        _require_role(
            [
                UserRole.ADMIN,
                UserRole.SHOP,
                UserRole.COURIER,
            ]
        )
    ),
]
