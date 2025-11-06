from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.shop import Shop
from backend.src.models.user import User
from backend.src.schemas.courier import CourierResponse
from backend.src.schemas.user import (
    CourierUserUpdate,
    ShopUserUpdate,
    UserCreateWithoutPassword,
    UserResponse,
    UserUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = get_logger(__name__)


async def get_user_or_none(db: AsyncSession, user_id: int) -> User | None:
    """Получить пользователя по ID, если существует."""
    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"Пользователь с ID {user_id} не найден.")
        return None
    return user


async def _update_profile(db: AsyncSession, user: User, data: dict, model: type) -> bool:
    """
    Универсальное обновление профиля (магазина или курьера).
    model — класс модели: Shop или Courier.
    """
    profile = await db.scalar(select(model).where(model.user_id == user.id))
    if not profile:
        logger.warning(f"Профиль {model.__name__} для пользователя {user.id} не найден.")
        return False

    for field, value in data.items():
        if hasattr(profile, field):
            setattr(profile, field, value)
        else:
            logger.warning(f"Попытка обновить несуществующее поле '{field}' в модели {model}")

    return True


async def update_my_profile(
    db: AsyncSession, user_id: int, profile_data: UserUpdate
) -> User | None:
    """Обновление профиля пользователя (магазина или курьера)."""
    logger.info(f"Обновление профиля пользователя ID: {user_id}")

    user = await get_user_or_none(db, user_id)
    if not user:
        return None

    # Берём только те поля, которые реально переданы
    update_data = profile_data.model_dump(exclude_unset=True)
    logger.debug(f"Данные для обновления: {update_data}")

    async with db.begin():
        if profile_data.role == UserRole.SHOP and isinstance(profile_data, ShopUserUpdate):
            ok = await _update_profile(db, user, update_data, Shop)
        elif profile_data.role == UserRole.COURIER and isinstance(profile_data, CourierUserUpdate):
            ok = await _update_profile(db, user, update_data, Courier)
        else:
            logger.error(f"Несоответствие роли и данных для пользователя {user_id}")
            return None

        if not ok:
            return None

    await db.refresh(user)
    logger.info(f"Профиль пользователя {user_id} успешно обновлён.")
    return user


async def get_all_couriers(db: AsyncSession) -> list[CourierResponse]:
    """
    Получение списка всех активных курьеров (для администраторов).

    Args:
        db: Сессия базы данных.

    Returns:
        Список всех курьеров.
    """
    logger.info("Запрос списка всех курьеров.")
    result = await db.execute(select(Courier).join(User))
    couriers = result.scalars().all()
    logger.debug(f"Найдено {len(couriers)} курьеров.")
    return [CourierResponse.model_validate(cour) for cour in couriers]


async def complete_user_registration(
    db: AsyncSession, user_id: int, user_data: UserCreateWithoutPassword
) -> UserResponse:
    """
    Завершить регистрацию пользователя после сбора данных в боте.
    Обновляет данные пользователя и создает связанную сущность (Shop или Courier).

    Args:
        db: Сессия базы данных.
        user_id: ID пользователя для завершения регистрации.
        user_data: Данные пользователя для обновления.

    Returns:
        Объект UserResponse с данными пользователя.

    Raises:
        ValueError: Если пользователь не найден.
    """
    logger.info(f"Завершение регистрации для пользователя с ID: {user_id}")
    async with db.begin():
        user = await db.get(User, user_id)
        if not user:
            logger.error(f"Пользователь с ID {user_id} не найден для завершения регистрации.")
            raise ValueError("Пользователь не найден")

        # Обновить данные пользователя
        update_data = user_data.model_dump(exclude_unset=True)
        logger.debug(f"Данные для завершения регистрации пользователя {user_id}: {update_data}")
        for field, value in update_data.items():
            setattr(user, field, value)

        # Создать связанную сущность (магазин или курьера)
        if user.role == UserRole.SHOP:
            shop = await db.scalar(select(Shop).where(Shop.user_id == user.id))
            if not shop:
                logger.info(f"Создание сущности Shop для пользователя {user.id}")
                db.add(Shop(user_id=user.id))
        elif user.role == UserRole.COURIER:
            courier = await db.scalar(select(Courier).where(Courier.user_id == user.id))
            if not courier:
                logger.info(f"Создание сущности Courier для пользователя {user.id}")
                db.add(Courier(user_id=user.id))
        else:
            raise ValueError("роль пользователя не корректна")

    await db.refresh(user)
    logger.info(f"Пользователь с ID {user_id} успешно завершил регистрацию как {user.role.value}.")
    return UserResponse.model_validate(user)
