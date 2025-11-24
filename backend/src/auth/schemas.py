from backend.src.common.enums import TokenType
from pydantic import BaseModel, Field


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
