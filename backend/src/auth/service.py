import math
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from backend.src.auth import exceptions
from backend.src.common.constants import (
    LOGIN_ATTEMPTS_KEY,
    LOGIN_LOCK_KEY,
    MAX_CODE_LENGTH,
    SECONDS_IN_MINUTE,
)
from backend.src.common.enums import UserRole
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.user import User
from backend.src.schemas.auth import AuthSuccessResponse, UserInfo
from jose import JWTError, jwt
from sqlalchemy import select, update
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
            "iat": datetime.now(UTC),
        }
        if getattr(user, "telegram_id", None) is not None:
            to_encode["tid"] = str(user.telegram_id)

        expire = datetime.now(UTC) + timedelta(minutes=settings.jwt.access_token_expire_minutes)
        to_encode["exp"] = expire

        try:
            return jwt.encode(
                to_encode,
                settings.jwt.secret_key.get_secret_value(),
                algorithm=settings.jwt.algorithm,
            )
        except Exception as e:
            logger.exception(f"Ошибка при создании JWT токена для пользователя {user.id}")
            raise JWTError(f"Не удалось создать токен: {e}")

    @staticmethod
    def _validate_input_data(telegram_id: int, code: str) -> None:
        """Валидирует входные данные."""
        AuthService._validate_telegram_id(telegram_id)
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
        if ttl is None or ttl < 0:
            return 0
        return max(1, math.ceil(ttl / SECONDS_IN_MINUTE)) if ttl > 0 else 0

    async def _is_user_locked(self, telegram_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь."""
        lock_key = LOGIN_LOCK_KEY.format(telegram_id=telegram_id)
        return bool(await self.redis.exists(lock_key))

    async def _handle_failed_attempt(self, telegram_id: int) -> None:
        """Обрабатывает неудачную попытку входа, увеличивая счетчик и блокируя при необходимости."""
        attempts_key = LOGIN_ATTEMPTS_KEY.format(telegram_id=telegram_id)
        current_attempts = await self.redis.incr(attempts_key)

        if current_attempts == 1:
            await self.redis.expire(attempts_key, settings.redis.default_ttl_seconds)

        attempts_left = settings.redis.registration_max_attempts - current_attempts

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
    def _validate_telegram_id(telegram_id: int) -> None:
        """Валидирует Telegram ID."""
        if not isinstance(telegram_id, int):
            raise ValueError("Некорректный Telegram ID")

    @staticmethod
    async def _create_guest_user(db: AsyncSession, telegram_id: int) -> User:
        """
        Создает нового пользователя с ролью GUEST.
        Использует SAVEPOINT для безопасной обработки гонки потоков при создании.
        """
        # Контекстный менеджер begin_nested() создает SAVEPOINT в текущей транзакции.
        async with db.begin_nested():
            new_guest_user = User(telegram_id=telegram_id, role=UserRole.GUEST)
            db.add(new_guest_user)
            try:
                # flush() отправляет команду INSERT в БД и позволяет получить new_guest_user.id.
                # Это необходимо, чтобы убедиться, что пользователь создан, и получить его ID.
                await db.flush()
                await db.refresh(new_guest_user)
                logger.info(
                    f"Создан новый ГОСТЬ с ID={new_guest_user.id} для telegram_id={telegram_id}"
                )
                return new_guest_user
            except IntegrityError:
                # Ошибка IntegrityError означает, что пользователь с таким telegram_id уже был создан
                # в параллельном запросе (гонка потоков).
                # При выходе из блока `begin_nested` с исключением произойдет автоматический
                # откат к SAVEPOINT, отменяя `db.add(new_guest_user)`.
                logger.warning(
                    f"Гонка при создании гостя для telegram_id={telegram_id}. Повторный поиск."
                )
                # Теперь сессия чиста, и мы можем безопасно найти того самого пользователя,
                # который был создан параллельно.
                user = await AuthService._find_existing_user(db, telegram_id)
                if user:
                    return user
                # Если пользователя все еще нет, это неожиданная ошибка.
                logger.error(
                    f"Не удалось получить или создать пользователя для telegram_id={telegram_id}"
                )
                raise

    @staticmethod
    async def get_user_by_telegram_id_or_create_guest(telegram_id: int, db: AsyncSession) -> User:
        """
        Находит пользователя по telegram_id. Если не найден - создает нового
        пользователя с ролью GUEST.

        Важно: функция не выполняет commit. Ответственность за commit на вызывающем коде.
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
    async def _consume_registration_code(
        db: AsyncSession, code: str, user_id: int
    ) -> UserRole | None:
        """
        Атомарно помечает код регистрации как использованный и возвращает роль.
        Возвращает None, если код не найден или уже использован.
        """
        res = await db.execute(
            update(RegistrationCode)
            .where(RegistrationCode.code == code, RegistrationCode.is_used.is_(False))
            .values(is_used=True, user_id=user_id)
            .returning(RegistrationCode.role)
        )
        row = res.first()
        return row[0] if row else None

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

        # Если пользователь уже зарегистрирован — обрабатываем как повторный вход.
        # Для обратной совместимости возвращаем через специальное исключение.
        if user and user.role not in [UserRole.PENDING, UserRole.GUEST]:
            access_token = AuthService.create_access_token(user)
            raise exceptions.UserAlreadyRegisteredError(
                detail="Пользователь уже зарегистрирован.",
                user_data={"id": user.id, "role": user.role.value},
                access_token=access_token,
            )

        try:
            async with db.begin():
                # Создать пользователя (если не существует), чтобы получить user.id
                if not user:
                    user = User(telegram_id=telegram_id)
                    db.add(user)
                    await db.flush()
                    logger.info(f"Создан новый пользователь с telegram_id={telegram_id}")

                # Атомарно "поглощаем" код и получаем связанную роль
                role = await AuthService._consume_registration_code(db, code, user.id)
                if not role:
                    # Невалидный или уже использованный код — увеличиваем счетчик попыток и кидаем ошибку
                    await self._handle_failed_attempt(telegram_id)

                # Успех: назначаем роль и снимаем блокировку у пользователя
                user.role = role  # type: ignore[assignment]
                user.is_blocked = False

            # После успешного коммита
            await db.refresh(user)
            await self._clear_login_attempts(telegram_id)

            role_name = getattr(user.role, "value", str(user.role))
            logger.info(f"Пользователь {telegram_id} успешно аутентифицирован с ролью {role_name}")

            access_token = AuthService.create_access_token(user)
            return AuthSuccessResponse(
                user=UserInfo(id=user.id, role=role_name),
                access_token=access_token,
            )
        except Exception:
            logger.exception(f"Ошибка при аутентификации {telegram_id}")
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
