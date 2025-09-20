from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.shop import Shop
from backend.src.models.user import User
from backend.src.schemas.courier import CourierResponse
from backend.src.schemas.user import UserCreateWithoutPassword, UserResponse, UserUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

MAX_ATTEMPTS = 3

logger = get_logger(__name__)





async def update_user(db: AsyncSession, user_id: int, user_data: UserUpdate) -> User | None:
    """
    Обновление данных пользователя по его ID.
    """
    user = await db.get(User, user_id)
    if not user:
        return None

    for field, value in user_data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


async def get_all_couriers(db: AsyncSession) -> list[CourierResponse]:
    """
    Получение списка всех активных курьеров (для администраторов).
    """
    result = await db.execute(select(Courier).join(User))
    couriers = result.scalars().all()
    return [CourierResponse.model_validate(cour) for cour in couriers]


async def complete_user_registration(
    db: AsyncSession, user_id: int, user_data: UserCreateWithoutPassword
) -> UserResponse:
    """
    Завершить регистрацию пользователя после сбора данных в боте.
    """
    user = await db.get(User, user_id)
    if not user:
        raise ValueError("Пользователь не найден")

    # Обновить данные пользователя
    for field, value in user_data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    # Создать связанную сущность (магазин или курьера)
    if user.role == UserRole.SHOP:
        shop = await db.scalar(select(Shop).where(Shop.user_id == user.id))
        if not shop:
            db.add(Shop(user_id=user.id, name="Default Shop", address=""))
    elif user.role == UserRole.COURIER:
        courier = await db.scalar(select(Courier).where(Courier.user_id == user.id))
        if not courier:
            db.add(Courier(user_id=user.id))

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
