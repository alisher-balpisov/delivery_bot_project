from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from backend.src.auth import exceptions
from backend.src.common.enums import UserRole, UserStatus
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
    Декодирует JWT токен, проверяет чёрный список и возвращает пользователя.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key.get_secret_value(),
            algorithms=[settings.jwt.algorithm],
        )

        # Проверяем тип токена
        token_type = payload.get("type")
        if token_type != "access":
            logger.warning("Попытка использовать не-access токен для API запроса")
            raise exceptions.CREDENTIALS_EXCEPTION

        sub = payload.get("sub")
        if sub is None:
            logger.warning("В токене отсутствует 'sub' (ID пользователя)")
            raise exceptions.CREDENTIALS_EXCEPTION

        try:
            user_id = int(sub)
        except (TypeError, ValueError):
            raise exceptions.CREDENTIALS_EXCEPTION

    except (JWTError, ValueError) as e:
        logger.warning(f"Ошибка декодирования/валидации JWT: {e}")
        raise exceptions.CREDENTIALS_EXCEPTION

    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"Пользователь с ID {user_id} из токена не найден в БД")
        raise exceptions.CREDENTIALS_EXCEPTION

    # Проверяем статус пользователя
    if user.status == UserStatus.INACTIVE:
        logger.warning(f"Неактивный пользователь {user.id} попытался получить доступ")
        raise exceptions.ACCOUNT_INACTIVE_EXCEPTION

    if user.status == UserStatus.BLOCKED:
        logger.warning(f"Заблокированный пользователь {user.id} попытался получить доступ")
        raise exceptions.ACCOUNT_BLOCKED_EXCEPTION

    logger.debug(f"Пользователь {user} аутентифицирован через JWT")
    return user


def _require_role(
    allowed_roles: UserRole | list[UserRole] | tuple[UserRole, ...],
) -> Callable[..., Coroutine[Any, Any, User]]:
    """
    Проверяет, что роль пользователя соответствует одной из разрешённых.
    """
    if isinstance(allowed_roles, UserRole):
        allowed_roles = [allowed_roles]

    async def _role_dependency(user: User = Depends(_get_current_user)) -> User:
        if user.role == UserRole.GUEST:
            logger.warning(f"У пользователя {user} роль GUEST — доступ запрещён")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав доступа.",
            )

        if user.role not in allowed_roles:
            logger.warning(
                f"Доступ запрещён для пользователя {user}: "
                f"роль {user.role.value} не входит в {[r.value for r in allowed_roles]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Недостаточно прав доступа. Требуется одна из ролей: {[r.value for r in allowed_roles]}",
            )

        if UserRole.SHOP in allowed_roles and user.role == UserRole.SHOP:
            if not user.shop:
                logger.warning(f"Пользователь {user} с ролью SHOP не имеет связанного магазина")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Недостаточно прав доступа: отсутствует связанный магазин.",
                )

        if UserRole.COURIER in allowed_roles and user.role == UserRole.COURIER:
            if not user.courier:
                logger.warning(f"Пользователь {user} с ролью COURIER не имеет связанного курьера")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Недостаточно прав доступа: отсутствует связанный курьер.",
                )

        logger.debug(f"Проверка роли пройдена для пользователь {user}")
        return user

    return _role_dependency


# Зависимости для конкретных ролей
RequireAdmin = Annotated[User, Depends(_require_role(UserRole.ADMIN))]
RequireShop = Annotated[User, Depends(_require_role(UserRole.SHOP))]
RequireCourier = Annotated[User, Depends(_require_role(UserRole.COURIER))]

# Зависимость для группы ролей
RequireShopOrCourier = Annotated[User, Depends(_require_role([UserRole.SHOP, UserRole.COURIER]))]
RequireAdminOrShop = Annotated[User, Depends(_require_role([UserRole.ADMIN, UserRole.SHOP]))]
RequireAdminOrCourier = Annotated[User, Depends(_require_role([UserRole.ADMIN, UserRole.COURIER]))]
RequireAllRoles = Annotated[
    User, Depends(_require_role([UserRole.ADMIN, UserRole.SHOP, UserRole.COURIER]))
]
