from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db
from src.auth.bot_auth import authenticate_bot
from src.common.enums import TokenType
from src.users.service import get_user_by_telegram_id

router = APIRouter()


class BotAuthRequest(BaseModel):
    api_key: str

    class Config:
        from_attributes = True


class BotAuthResponse(BaseModel):
    access_token: str
    token_type: str = TokenType.BEARER


@router.post("/bot/token", response_model=BotAuthResponse)
async def get_bot_token(auth_data: BotAuthRequest):
    """
    Получить JWT токен для бота по API ключу.
    Этот endpoint используется ботом при запуске для получения долгоживущего токена.
    """
    try:
        access_token = authenticate_bot(auth_data.api_key)
        return BotAuthResponse(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e!s}")


async def get_current_user_telegram_id(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """
    Dependency для получения текущего пользователя по telegram_id.
    Используется в защищенных endpoint'ах вместо JWT токенов пользователей.
    """
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user
