from datetime import datetime, timedelta

import redis.asyncio as aioredis
from backend.src.auth import exceptions
from backend.src.common.constants import (
    LOGIN_ATTEMPTS_KEY,
    LOGIN_LOCK_KEY,
    MAX_CODE_LENGTH,
    MAX_TELEGRAM_ID,
    MIN_TELEGRAM_ID,
    SECONDS_IN_MINUTE,
)
from backend.src.common.enums import UserRole
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.user import User
from backend.src.schemas.auth import AuthSuccessResponse, UserInfo
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class AuthService:
    """Сервис для работы с аутентификацией и авторизацией."""

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    @staticmethod
    def create_access_token(user: User) -> str:
        """
        Создает новый JWT токен для пользователя.

        Args:
            user: Пользователь, для которого создается токен

        Returns:
            JWT токен в виде строки

        Raises:
            JWTError: Если произошла ошибка при создании токена
        """
        if not user or not user.id:
            raise ValueError("Пользователь должен иметь валидный ID")

        to_encode = {
            "sub": str(user.id),
            "role": user.role.value,
            "tid": str(user.telegram_id),
            "iat": datetime.utcnow(),
        }
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt.access_token_expire_minutes)
        to_encode["exp"] = expire

        try:
            return jwt.encode(
                to_encode,
                settings.jwt.secret_key.get_secret_value(),
                algorithm=settings.jwt.algorithm,
            )
        except Exception as e:
            logger.error(f"Ошибка при создании JWT токена для пользователя {user.id}: {e}")
            raise JWTError(f"Не удалось создать токен: {e}")

    @staticmethod
    def _validate_input_data(telegram_id: int, code: str) -> None:
        """Валидирует входные данные."""
        if (
            not isinstance(telegram_id, int)
            or telegram_id < MIN_TELEGRAM_ID
            or telegram_id > MAX_TELEGRAM_ID
        ):
            raise ValueError("Некорректный Telegram ID")

        if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE_LENGTH:
            raise ValueError("Некорректный код регистрации")

    @staticmethod
    def _mask_sensitive_data(code: str) -> str:
        """Маскирует чувствительные данные для логирования."""
        if len(code) <= 2:
            return "*" * len(code)
        return code[0] + "*" * (len(code) - 2) + code[-1]

    async def _get_lock_duration_minutes(self, telegram_id: int) -> int:
        """Получает оставшееся время блокировки в минутах."""
        lock_key = LOGIN_LOCK_KEY.format(telegram_id=telegram_id)
        ttl = await self.redis.ttl(lock_key)
        return max(1, ttl // SECONDS_IN_MINUTE + 1) if ttl > 0 else 0

    async def _is_user_locked(self, telegram_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь."""
        lock_key = LOGIN_LOCK_KEY.format(telegram_id=telegram_id)
        return await self.redis.exists(lock_key) > 0

    async def _handle_failed_attempt(self, telegram_id: int) -> None:
        """Обрабатывает неудачную попытку входа, увеличивая счетчик и блокируя при необходимости."""
        attempts_key = LOGIN_ATTEMPTS_KEY.format(telegram_id=telegram_id)
        current_attempts = await self.redis.incr(attempts_key)

        if current_attempts == 1:
            await self.redis.expire(attempts_key, settings.redis.default_ttl_seconds)

        attempts_left = settings.business.registration_max_attempts - current_attempts

        if attempts_left > 0:
            logger.info(
                f"Неудачная попытка входа для {telegram_id}. Осталось попыток: {attempts_left}"
            )
            raise exceptions.InvalidCredentialsError(
                f"Неверный код. Осталось попыток: {attempts_left}"
            )
        else:
            await self._lock_user(telegram_id)
            await self.redis.delete(attempts_key)

            lock_duration_min = settings.redis.default_ttl_seconds // SECONDS_IN_MINUTE
            logger.warning(f"Пользователь {telegram_id} заблокирован на {lock_duration_min} минут")
            raise exceptions.AttemptsLimitExceededError(
                f"Превышено количество попыток. Попробуйте снова через {lock_duration_min} минут."
            )

    async def _lock_user(self, telegram_id: int) -> None:
        """Блокирует пользователя на определенное время."""
        lock_key = LOGIN_LOCK_KEY.format(telegram_id=telegram_id)
        await self.redis.set(lock_key, "locked", ex=settings.redis.default_ttl_seconds)

    async def _clear_login_attempts(self, telegram_id: int) -> None:
        """Очищает счетчик попыток входа для пользователя."""
        attempts_key = LOGIN_ATTEMPTS_KEY.format(telegram_id=telegram_id)
        await self.redis.delete(attempts_key)

    @staticmethod
    async def _find_existing_user(db: AsyncSession, telegram_id: int) -> User | None:
        """Ищет существующего пользователя по telegram_id."""
        return await db.scalar(select(User).where(User.telegram_id == telegram_id))

    @staticmethod
    async def _find_valid_registration_code(db: AsyncSession, code: str) -> RegistrationCode | None:
        """Ищет валидный код регистрации."""
        return await db.scalar(
            select(RegistrationCode).where(
                RegistrationCode.code == code,
                RegistrationCode.is_used.is_(False),
            )
        )

    @staticmethod
    def _validate_telegram_id(telegram_id: int) -> None:
        """Валидирует Telegram ID."""
        if not isinstance(telegram_id, int) or not (
            MIN_TELEGRAM_ID <= telegram_id <= MAX_TELEGRAM_ID
        ):
            raise ValueError("Некорректный Telegram ID")

    @staticmethod
    async def _create_guest_user(db: AsyncSession, telegram_id: int) -> User:
        """Создает нового пользователя с ролью GUEST."""
        new_guest_user = User(telegram_id=telegram_id, role=UserRole.GUEST)
        db.add(new_guest_user)

        try:
            await db.flush()
            await db.refresh(new_guest_user)
            logger.info(
                f"Создан новый ГОСТЬ с ID={new_guest_user.id} для telegram_id={telegram_id}"
            )
            return new_guest_user
        except IntegrityError as e:
            await db.rollback()
            logger.warning(
                f"Гонка при создании гостя для telegram_id={telegram_id}. Повторный поиск."
            )
            user = await AuthService._find_existing_user(db, telegram_id)
            if user:
                return user
            logger.error(
                f"Не удалось получить или создать пользователя для telegram_id={telegram_id}"
            )
            raise e

    @staticmethod
    async def get_user_by_telegram_id_or_create_guest(telegram_id: int, db: AsyncSession) -> User:
        """
        Находит пользователя по telegram_id. Если не найден - создает нового
        пользователя с ролью GUEST.
        """
        AuthService._validate_telegram_id(telegram_id)
        user = await AuthService._find_existing_user(db, telegram_id)
        if user:
            return user
        return await AuthService._create_guest_user(db, telegram_id)

    @staticmethod
    async def _create_or_update_user(
        db: AsyncSession, user: User | None, telegram_id: int, role: UserRole
    ) -> User:
        """Создает нового пользователя или обновляет существующего."""
        if not user:
            user = User(telegram_id=telegram_id)
            db.add(user)
            await db.flush()
            logger.info(f"Создан новый пользователь с telegram_id={telegram_id}")

        user.role = role
        user.is_blocked = False
        return user

    @staticmethod
    async def _mark_code_as_used(registration_code: RegistrationCode, user_id: int) -> None:
        """Помечает код регистрации как использованный."""
        registration_code.is_used = True
        registration_code.user_id = user_id

    async def auth_by_code(
        self, db: AsyncSession, telegram_id: int, code: str
    ) -> AuthSuccessResponse:
        """
        Обрабатывает регистрацию/аутентификацию пользователя по коду приглашения.
        """
        AuthService._validate_input_data(telegram_id, code)
        masked_code = AuthService._mask_sensitive_data(code)
        logger.info(f"Попытка аутентификации {telegram_id} с кодом {masked_code}")

        if await self._is_user_locked(telegram_id):
            lock_duration_min = await self._get_lock_duration_minutes(telegram_id)
            raise exceptions.AccountLockedError(
                f"Превышено количество попыток. Попробуйте снова через {lock_duration_min} минут."
            )

        user = await AuthService._find_existing_user(db, telegram_id)

        # Если пользователь уже зарегистрирован, это не ошибка, а повторный вход.
        # Выбрасываем особое исключение с токеном, чтобы вызывающий код
        # мог обработать этот случай как успешный логин.
        if user and user.role not in [UserRole.PENDING, UserRole.GUEST]:
            access_token = AuthService.create_access_token(user)
            raise exceptions.UserAlreadyRegisteredError(
                detail="Пользователь уже зарегистрирован.",
                user_data={"id": user.id, "role": user.role.value},
                access_token=access_token,
            )

        registration_code = await AuthService._find_valid_registration_code(db, code)
        if not registration_code:
            await self._handle_failed_attempt(telegram_id)

        logger.info(f"Найден валидный код для {telegram_id}, роль: {registration_code.role.value}")

        try:
            user = await AuthService._create_or_update_user(
                db, user, telegram_id, registration_code.role
            )
            await AuthService._mark_code_as_used(registration_code, user.id)
            await db.commit()
            await db.refresh(user)
            await self._clear_login_attempts(telegram_id)

            logger.info(
                f"Пользователь {telegram_id} успешно аутентифицирован с ролью {user.role.value}"
            )

            access_token = AuthService.create_access_token(user)
            return AuthSuccessResponse(
                user=UserInfo(id=user.id, role=user.role.value),
                access_token=access_token,
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка при аутентификации {telegram_id}: {e}")
            raise


# Вспомогательные функции для обратной совместимости
def create_access_token(user: User) -> str:
    """Создает новый JWT токен (функция для обратной совместимости)."""
    return AuthService.create_access_token(user)


async def auth_by_code(
    db: AsyncSession, redis: aioredis.Redis, telegram_id: int, code: str
) -> AuthSuccessResponse:
    """Обрабатывает регистрацию/аутентификацию по коду (функция для обратной совместимости)."""
    auth_service = AuthService(redis)
    return await auth_service.auth_by_code(db, telegram_id, code)


async def get_user_by_telegram_id_or_create_guest(telegram_id: int, db: AsyncSession) -> User:
    """Находит или создает пользователя-гостя (функция для обратной совместимости)."""
    return await AuthService.get_user_by_telegram_id_or_create_guest(telegram_id, db)
