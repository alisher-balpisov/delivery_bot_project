from backend.src.common.enums import TokenType
from pydantic import BaseModel


class Token(BaseModel):
    """Схема для ответа с JWT токеном."""

    access_token: str
    token_type: str = TokenType.BEARER.value


class TokenData(BaseModel):
    """Схема для данных, закодированных в JWT."""

    user_id: int | None = None
    role: str | None = None
    telegram_id: int | None = None


class TokenRequest(BaseModel):
    """Схема для запроса токена по telegram_id."""

    telegram_id: int


class AuthByCodeRequest(BaseModel):
    """Схема для запроса аутентификации по коду."""

    telegram_id: int
    code: str


class UserInfo(BaseModel):
    id: int
    role: str


class AuthSuccessResponse(BaseModel):
    user: UserInfo
    access_token: str
    already_registered: bool = False
