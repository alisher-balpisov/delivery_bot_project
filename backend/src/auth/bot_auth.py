from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from src.common.enums import TokenType
from src.core.config import settings

# Схема для хэширования API ключей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token схема
security = HTTPBearer()


def get_password_hash(password: str) -> str:
    """Получить хэш пароля"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверить пароль"""
    return pwd_context.verify(plain_password, hashed_password)


def create_bot_access_token(data: dict, expires_delta: timedelta | None = None):
    """Создать JWT токен для бота"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        # Токен бота действует дольше - 24 часа по умолчанию
        expire = datetime.now() + timedelta(hours=24)

    to_encode.update({"exp": expire, "type": TokenType.BOT})
    encoded_jwt = jwt.encode(
        to_encode, settings.auth.jwt_secret.get_secret_value(), algorithm=settings.auth.jwt_algorithm
    )
    return encoded_jwt


def authenticate_bot(api_key: str) -> str:
    """
    Аутентифицировать бота по API ключу и вернуть JWT токен.
    В продакшене API ключ должен храниться в защищенной переменной окружения.
    """
    # Простая проверка - в реальности ключ должен храниться в БД или секретах
    expected_key = settings.auth.bot_api_key or "test_bot_key"

    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный API ключ бота"
        )

    # Создать JWT токен для бота
    access_token = create_bot_access_token(data={"sub": "bot"})
    return access_token


def verify_bot_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Проверить JWT токен бота.
    Используется как dependency в защищенных endpoint'ах.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить токен бота",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.auth.jwt_secret.get_secret_value(),
            algorithms=[settings.auth.jwt_algorithm],
        )

        # Проверить тип токена
        token_type = payload.get("type")
        if token_type != TokenType.BOT:
            raise credentials_exception

        return payload

    except JWTError:
        raise credentials_exception


async def get_bot_token(api_key: str):
    """
    Получить JWT токен для бота.
    Этот endpoint может использоваться ботом при запуске для получения долгоживущего токена.
    """
    return authenticate_bot(api_key)
