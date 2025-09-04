from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.schemas.shop import ShopRegistration
from src.schemas.user import UserRead
from src.users import service

router = APIRouter()


@router.post("/register/shop", response_model=UserRead, status_code=201)
async def register_shop_user(
    registration_data: ShopRegistration, db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя с ролью "магазин" и создание профиля магазина.
    """
    # TODO: Добавить проверку на существование пользователя по telegram_id или phone
    # user = await service.get_user_by_telegram_id(db, registration_data.telegram_id)
    # if user:
    #     raise HTTPException(status_code=400, detail="User with this Telegram ID already exists")

    new_user = await service.register_shop(db=db, registration_data=registration_data)
    return new_user


@router.get("/{telegram_id}", response_model=UserRead)
async def get_user_profile(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получение профиля пользователя по Telegram ID.
    """
    user = await service.get_user_by_telegram_id(db=db, telegram_id=telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
