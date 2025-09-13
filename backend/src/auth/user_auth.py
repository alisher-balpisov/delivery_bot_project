from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Any

from backend.src.common.enums import UserRole
from backend.src.core.config import settings
from backend.src.core.database import get_db
from backend.src.users.service import get_user_by_telegram_id
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

logger = getLogger(__name__)
bearer_scheme = HTTPBearer()


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """
    Создает JWT токен доступа с дополнительными claims.

    Args:
        data: Данные для включения в токен (должен содержать 'sub')
        expires_delta: Время жизни токена (опционально)

    Returns:
        str: Закодированный JWT токен
    """
    to_encode = data.copy()

    # Устанавливаем время выдачи (UTC timezone-aware)
    issued_at = datetime.now(UTC)
    to_encode.update({"iat": issued_at.timestamp()})  # Хранить как timestamp

    # Устанавливаем время истечения
    if expires_delta:
        expire = issued_at + expires_delta
    else:
        expire = issued_at + timedelta(minutes=settings.auth.access_token_expire_minutes)

    to_encode.update({"exp": expire.timestamp()})  # Хранить как timestamp

    # Добавляем тип токена
    to_encode.update({"type": "access"})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.auth.jwt_secret.get_secret_value(),
        algorithm=settings.auth.jwt_algorithm,
    )

    logger.debug(
        f"Создан токен для пользователя {data.get('sub', 'unknown')} с истечением {expire}"
    )
    return encoded_jwt


def decode_access_token(token: str):
    """
    Декодирует и валидирует JWT токен с дополнительными проверками.

    Args:
        token: JWT токен для декодирования

    Returns:
        dict: Декодированный payload токена

    Raises:
        HTTPException: При ошибках валидации токена
    """
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен отсутствует или неверного формата",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret.get_secret_value(),
            algorithms=[settings.auth.jwt_algorithm],
        )

        # Дополнительная проверка на наличие обязательных полей
        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Токен не содержит необходимую информацию",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Проверка на будущую дату выдачи (iat)
        iat = payload.get("iat")
        if iat:
            current_time = datetime.now(UTC).timestamp()
            if iat > current_time + 60:  # Токен выдан в будущем (с запасом 1 минуту)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Токен выдан в будущем",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        logger.debug(f"Токен успешно декодирован для пользователя: {payload.get('sub')}")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning(
            f"Истек срок действия токена для пользователя: {payload.get('sub') if 'payload' in locals() else 'неизвестен'}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия токена истек",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError as e:
        logger.warning(f"Невалидный токен: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при декодировании токена: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка валидации токена",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: str = Depends(bearer_scheme), db: AsyncSession = Depends(get_db)
) -> Any:
    payload = decode_access_token(token.credentials)
    telegram_id_str = payload.get("sub")
    if telegram_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        telegram_id = int(telegram_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_telegram_id(db, telegram_id)
    if user is None:
        logger.warning(f"User not found by telegram_id {telegram_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Проверка активации пользователя
    if not user.is_active:
        logger.warning(f"Inactive user {telegram_id} attempted access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт отключен",
        )

    if user.is_blocked:
        logger.warning(f"Blocked user {telegram_id} attempted access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )

    logger.info(f"User {telegram_id} authenticated, role: {user.role.value}")
    return user


def require_role(required_role: str):
    """
    Декоратор для проверки роли пользователя.

    Args:
        required_role: Требуемая роль ('admin', 'shop', 'courier')

    Returns:
        Зависимость FastAPI
    """

    async def role_dependency(user=Depends(get_current_user)):
        if user.role.value != required_role:
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


# Короткие алиасы для удобства
def require_admin():
    return require_role(UserRole.ADMIN)


def require_shop():
    return require_role(UserRole.SHOP)


def require_courier():
    return require_role(UserRole.COURIER)
