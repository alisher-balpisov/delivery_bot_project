from backend.src.common.enums import TokenType
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger


class Token(BaseModel):
    """Схема для ответа с JWT токеном."""

    access_token: str
    token_type: str = TokenType.BEARER.value


class TokenData(BaseModel):
    """Схема для данных, закодированных в JWT."""

    user_id: int | None = None
    role: str | None = None
    telegram_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class TokenRequest(BaseModel):
    """Схема для запроса токена по telegram_id."""

    telegram_id: int


class AuthByCodeRequest(BaseModel):
    """Схема для запроса аутентификации по коду."""

    telegram_id: int
    code: str
    username: str | None


class UserInfo(BaseModel):
    id: int
    role: str


class LoginRequest(BaseModel):
    """Схема запроса для входа существующего пользователя."""

    telegram_id: int


class AuthSuccessResponse(BaseModel):
    """Ответ при успешной аутентификации"""

    user: UserInfo
    access_token: str
    refresh_token: str
    token_type: TokenType = TokenType.BEARER
    expires_in: int
    refresh_expires_in: int
    already_registered: bool = False


class RefreshTokenRequest(BaseModel):
    """Запрос на обновление токена"""

    refresh_token: str = Field(..., description="Refresh токен")


class RefreshTokenResponse(BaseModel):
    """Ответ с новой парой токенов"""

    access_token: str
    refresh_token: str
    token_type: TokenType = TokenType.BEARER
    expires_in: int
    refresh_expires_in: int
