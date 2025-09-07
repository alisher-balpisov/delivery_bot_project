from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import create_access_token
from src.common.enums import TokenType
from src.core.database import get_db
from src.schemas.registration_code import CodeActivationRequest
from src.schemas.shop import ShopRegistration
from src.schemas.user import UserCreateWithoutPassword, UserRead
from src.users import service


class LoginRequest(BaseModel):
    telegram_id: int
    # В будущем можно добавить пароль


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = TokenType.BEARER


class ActivationResponse(BaseModel):
    user_id: int
    telegram_id: int
    role: str
    is_registered: bool


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Вход в систему и получение JWT токена.
    """
    user = await service.get_user_by_telegram_id(db=db, telegram_id=login_data.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Создать токен
    access_token = create_access_token(data={"sub": str(user.telegram_id)})
    return TokenResponse(access_token=access_token)


@router.post("/register/shop", response_model=UserRead, status_code=201)
async def register_shop_user(
    registration_data: ShopRegistration, db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя с ролью "магазин" и создание профиля магазина.
    """
    # Проверить существование пользователя по telegram_id
    user = await service.get_user_response_by_telegram_id(db, registration_data.telegram_id)
    if user:
        raise HTTPException(
            status_code=400, detail="Пользователь с таким Telegram ID уже существует"
        )

    new_user = await service.register_shop(db=db, registration_data=registration_data)
    return new_user


@router.get("/{telegram_id}", response_model=UserRead)
async def get_user_profile(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получение профиля пользователя по Telegram ID.
    """
    user = await service.get_user_by_telegram_id(db=db, telegram_id=telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.post("/register", response_model=ActivationResponse)
async def register_user(activation_data: CodeActivationRequest, db: AsyncSession = Depends(get_db)):
    """
    Регистрация нового пользователя через одноразовый код приглашения.
    Совпадает с описанием: привязывает telegram_id к роли через invite_code.
    """
    try:
        result = await service.activate_registration_code(
            db=db,
            telegram_id=activation_data.telegram_id,
            code=activation_data.code,
            role=activation_data.role,
        )
        return ActivationResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/complete-registration/{telegram_id}", response_model=UserRead)
async def complete_user_registration(
    telegram_id: int, user_data: UserCreateWithoutPassword, db: AsyncSession = Depends(get_db)
):
    """
    Завершение регистрации после сбора данных в боте.
    """
    try:
        user = await service.complete_user_registration(
            db=db, telegram_id=telegram_id, user_data=user_data
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
