from datetime import UTC, datetime, timedelta

from backend.src.core.logging import get_logger
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from src.core.config import settings

# Контекст для хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = get_logger(__name__)


class TokenData(BaseModel):
    telegram_id: int | None = None
    email: str | None = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверить пароль"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Получить хэш пароля"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Создать JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)  # Default 15 minutes

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.auth.jwt_secret.get_secret_value(),
        algorithm=settings.auth.jwt_algorithm,
    )
    return encoded_jwt


def verify_token(token: str) -> TokenData | None:
    """Верифицировать JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret.get_secret_value(),
            algorithms=[settings.auth.jwt_algorithm],
        )
        sub: str = payload.get("sub")
        if sub is None:
            return None
        try:
            telegram_id = int(sub)
            return TokenData(telegram_id=telegram_id)
        except ValueError:
            return TokenData(email=sub)
    except JWTError:
        return None
