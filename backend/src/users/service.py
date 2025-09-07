# src/users/service.py
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.common.enums import UserRole
from src.models.courier import Courier
from src.models.registration_code import RegistrationCode
from src.models.shop import Shop
from src.models.user import User
from src.schemas.courier import CourierResponse
from src.schemas.shop import ShopCreate
from src.schemas.user import UserCreate, UserCreateWithoutPassword, UserResponse, UserUpdate


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
    """
    Поиск пользователя по Telegram ID.
    Проверяет активность и блокировку пользователя.
    """
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalars().first()

    if user:
        if user.is_blocked:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if not user.is_active:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

    return user


async def get_user_response_by_telegram_id(
    db: AsyncSession, telegram_id: int
) -> UserResponse | None:
    """
    Поиск пользователя по Telegram ID с возвратом Pydantic модели.
    """
    user = await get_user_by_telegram_id(db, telegram_id)
    if user:
        return UserResponse.model_validate(user)
    return None


async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """
    Создание нового пользователя в системе.
    """
    user = User(
        telegram_id=user_data.telegram_id,
        name=user_data.name,
        phone=user_data.phone,
        role=user_data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, telegram_id: int, user_data: UserUpdate) -> User | None:
    """
    Обновление данных пользователя по Telegram ID.
    """
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        return None

    for field, value in user_data.dict(exclude_unset=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


async def validate_registration_code(
    db: AsyncSession, telegram_id: int, code: str, role: UserRole
) -> RegistrationCode:
    """
    Валидация кода регистрации для пользователя.
    Ответственен за блокировку после 3 неудачных попыток.
    """
    # Проверить остановку пользователя
    user = await get_user_by_telegram_id(db, telegram_id)
    if user and user.is_blocked:
        raise ValueError("Пользователь заблокирован после 3 неудачных попыток.")

    # Найти код
    result = await db.execute(
        select(RegistrationCode).where(
            RegistrationCode.code == code,
            RegistrationCode.role == role,
            RegistrationCode.is_used is False,
        )
    )
    reg_code = result.scalars().first()

    if not reg_code:
        # Увеличить счетчик попыток
        if user:
            user.registration_attempts += 1
            if user.registration_attempts >= 3:
                user.is_blocked = True
            await db.commit()
        else:
            # Создать временного пользователя для учета попыток
            temp_user = User(telegram_id=telegram_id, role=role, registration_attempts=1)
            db.add(temp_user)
            await db.commit()
        raise ValueError("Неверный код регистрации.")

    # Код валиден
    if user:
        user.registration_attempts = 0  # Сбросить попытки
        user.registration_code_id = reg_code.id
        reg_code.is_used = True
        reg_code.user_id = user.id
        await db.commit()

    return reg_code


async def register_shop(
    db: AsyncSession, telegram_id: int, code: str, shop_data: ShopCreate, user_data: UserCreate
) -> UserResponse:
    """
    Регистрация нового магазина с валидацией кода.
    """
    # Проверить код
    reg_code = await validate_registration_code(db, telegram_id, code, UserRole.shop)

    # Создать пользователя
    user_data.role = UserRole.shop
    user = User(
        telegram_id=telegram_id,
        name=user_data.name,
        phone=user_data.phone,
        role=UserRole.shop,
        registration_code_id=reg_code.id,
        registration_attempts=0,
    )
    db.add(user)
    await db.flush()

    # Создать магазин
    shop = Shop(
        user_id=user.id,
        name=shop_data.name,
        address=shop_data.address or "",
    )
    db.add(shop)

    # Обновить код
    reg_code.user_id = user.id
    reg_code.is_used = True

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


async def register_courier(
    db: AsyncSession, telegram_id: int, code: str, user_data: UserCreate
) -> UserResponse:
    """
    Регистрация нового курьера с валидацией кода.
    """
    # Проверить код
    reg_code = await validate_registration_code(db, telegram_id, code, UserRole.courier)

    # Создать пользователя
    user_data.role = UserRole.courier
    user = User(
        telegram_id=user_data.telegram_id,
        name=user_data.name,
        phone=user_data.phone,
        role=UserRole.courier,
        registration_code_id=reg_code.id,
        registration_attempts=0,
    )
    db.add(user)
    await db.flush()

    # Создать курьера
    courier = Courier(user_id=user.id)
    db.add(courier)

    # Обновить код
    reg_code.user_id = user.id
    reg_code.is_used = True

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


async def get_all_couriers(db: AsyncSession) -> list[CourierResponse]:
    """
    Получение списка всех активных курьеров (для администраторов).
    """
    result = await db.execute(select(Courier).join(User))
    couriers = result.scalars().all()
    return [CourierResponse.model_validate(cour) for cour in couriers]


async def activate_registration_code(
    db: AsyncSession, telegram_id: int, code: str, role: UserRole
) -> dict:
    """
    Активировать одноразовый код регистрации.
    Создает базовую запись пользователя без данных - данные будут собраны позже в боте.
    """
    # Проверить код
    reg_code = await validate_registration_code(db, telegram_id, code, role)

    # Создать базовую запись пользователя без данных
    user = User(
        telegram_id=telegram_id,
        role=role,
        registration_code_id=reg_code.id,
        registration_attempts=0,
    )
    db.add(user)
    await db.flush()

    # Обновить код
    reg_code.user_id = user.id
    reg_code.is_used = True

    await db.commit()

    return {
        "user_id": user.id,
        "telegram_id": telegram_id,
        "role": role.value,
        "is_registered": False,  # Флаг что данные еще не собраны
    }


async def complete_user_registration(
    db: AsyncSession, telegram_id: int, user_data: UserCreateWithoutPassword
) -> UserResponse:
    """
    Завершить регистрацию пользователя после сбора данных в боте.
    """
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise ValueError("Пользователь не найден")

    # Обновить данные пользователя
    for field, value in user_data.dict(exclude_unset=True).items():
        setattr(user, field, value)

    # Создать связанную сущность (магазин или курьера)
    if user.role.value == "shop":
        shop = Shop(user_id=user.id, name="", address="")
        db.add(shop)
    elif user.role.value == "courier":
        courier = Courier(user_id=user.id)
        db.add(courier)

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
