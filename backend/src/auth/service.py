from datetime import datetime, timedelta

import redis.asyncio as aioredis
from backend.src.auth.eceptions import (
    AccountLockedError,
    AttemptsLimitExceededError,
    InvalidCredentialsError,
    UserAlreadyRegisteredError,
)
from backend.src.common.enums import UserRole
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.user import User
from backend.src.schemas.auth import AuthSuccessResponse, UserInfo
from jose import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Константы для ключей Redis
LOGIN_ATTEMPTS_KEY = "login_attempts:{telegram_id}"
LOGIN_LOCK_KEY = "login_lock:{telegram_id}"


def create_access_token(user: User) -> str:
    """Создает новый JWT токен для пользователя."""
    to_encode = {
        "sub": str(user.id),
        "role": user.role.value,
        "tid": str(user.telegram_id),
    }
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt.access_token_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(
        to_encode, settings.jwt.secret_key.get_secret_value(), algorithm=settings.jwt.algorithm
    )


async def _handle_failed_attempt(redis: aioredis.Redis, telegram_id: int):
    """Обрабатывает неудачную попытку входа, увеличивая счетчик и блокируя при необходимости."""
    attempts_key = LOGIN_ATTEMPTS_KEY.format(telegram_id=telegram_id)
    current_attempts = await redis.incr(attempts_key)

    if current_attempts == 1:
        await redis.expire(attempts_key, settings.redis.default_ttl_seconds)

    attempts_left = settings.business.registration_max_attempts - current_attempts

    if attempts_left > 0:
        logger.info(f"У пользователя {telegram_id} осталось {attempts_left} попыток.")
        raise InvalidCredentialsError(f"Неверный код. Осталось попыток: {attempts_left}")
    else:
        logger.warning(f"Пользователь {telegram_id} заблокирован из-за превышения попыток.")
        lock_key = LOGIN_LOCK_KEY.format(telegram_id=telegram_id)
        await redis.set(lock_key, "locked", ex=settings.redis.default_ttl_seconds)
        await redis.delete(attempts_key)
        lock_duration_min = settings.redis.default_ttl_seconds // 60
        raise AttemptsLimitExceededError(
            f"Превышено количество попыток. Попробуйте снова через {lock_duration_min} минут."
        )


async def auth_by_code(
    db: AsyncSession, redis: aioredis.Redis, telegram_id: int, code: str
) -> AuthSuccessResponse:
    """
    Обрабатывает регистрацию/аутентификацию пользователя по коду приглашения.

    При успехе возвращает AuthSuccessResponse.
    При ошибках выбрасывает кастомные исключения.
    """
    # 1. Проверка, не заблокирован ли пользователь из-за предыдущих попыток
    lock_key = LOGIN_LOCK_KEY.format(telegram_id=telegram_id)
    if await redis.exists(lock_key):
        ttl = await redis.ttl(lock_key)
        lock_duration_min = ttl // 60 + 1
        logger.warning(f"Попытка входа от заблокированного пользователя {telegram_id}.")
        raise AccountLockedError(
            f"Превышено количество попыток. Попробуйте снова через {lock_duration_min} минут."
        )

    # 2. Проверка, не зарегистрирован ли пользователь уже
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user and user.role not in [UserRole.PENDING, UserRole.GUEST]:
        logger.info(f"Пользователь {telegram_id} уже зарегистрирован с ролью {user.role.value}.")
        access_token = create_access_token(user)
        raise UserAlreadyRegisteredError(
            detail="Пользователь уже зарегистрирован.",
            user_data={"id": user.id, "role": user.role.value},
            access_token=access_token,
        )

    # 3. Поиск кода регистрации
    registration_code = await db.scalar(
        select(RegistrationCode).where(
            RegistrationCode.code == code,
            RegistrationCode.is_used.is_(False),
        )
    )

    # 4. Если код неверный или использован
    if not registration_code:
        logger.warning(f"Пользователь {telegram_id} ввел неверный/использованный код: {code}.")
        await _handle_failed_attempt(redis, telegram_id)
        # Строка ниже не будет достигнута, т.к. _handle_failed_attempt всегда выбрасывает исключение
        return  # type: ignore

    # 5. Успешная аутентификация
    logger.info(
        f"Для пользователя {telegram_id} найден валидный код: {code}, роль: {registration_code.role.value}."
    )

    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        await db.flush()

    user.role = registration_code.role
    user.is_blocked = False
    registration_code.is_used = True
    registration_code.user_id = user.id

    await db.commit()
    await db.refresh(user)  # Обновляем объект user данными из БД

    logger.info(
        f"Пользователь {telegram_id} успешно зарегистрирован. Код {code} помечен как использованный."
    )

    # Удаляем ключ с попытками из Redis при успехе
    await redis.delete(LOGIN_ATTEMPTS_KEY.format(telegram_id=telegram_id))

    access_token = create_access_token(user)
    return AuthSuccessResponse(
        user=UserInfo(id=user.id, role=user.role.value),
        access_token=access_token,
    )


async def get_user_by_telegram_id_or_create_guest(telegram_id: int, db: AsyncSession) -> User:
    """
    Находит пользователя по telegram_id. Если не найден - создает нового
    пользователя с ролью GUEST.
    """
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        return user

    logger.info(f"User with telegram_id {telegram_id} not found. Creating a new GUEST user.")
    new_guest_user = User(telegram_id=telegram_id, role=UserRole.GUEST)
    db.add(new_guest_user)
    try:
        await db.commit()
        await db.refresh(new_guest_user)
        return new_guest_user
    except IntegrityError:
        await db.rollback()
        user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
        if user:
            return user
        # Если все равно не удалось, значит, проблема серьезнее
        logger.error(
            f"Failed to retrieve or create user for telegram_id={telegram_id} after race condition."
        )
        raise  # Перевыбрасываем исходное исключение
