import math
from datetime import UTC, datetime, timedelta

from backend.src.auth import exceptions
from backend.src.common.constants import MAX_CODE_LENGTH, SECONDS_IN_MINUTE
from backend.src.common.enums import UserRole, UserStatus
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
            logger.exception(f"Ошибка при создании JWT токена для пользователя {user}")
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

    @staticmethod
    def _get_lock_duration_minutes(user: User) -> int:
        """Получает оставшееся время блокировки в минутах из поля locked_until."""
        if not user.locked_until or user.locked_until <= datetime.now(UTC):
            return 0

        ttl_seconds = (user.locked_until - datetime.now(UTC)).total_seconds()
        return max(1, math.ceil(ttl_seconds / SECONDS_IN_MINUTE))

    @staticmethod
    def _is_user_locked(user: User) -> bool:
        """Проверяет, заблокирован ли пользователь."""
        return user.status == UserStatus.BLOCKED

    @staticmethod
    async def _handle_failed_attempt(db: AsyncSession, user: User) -> None:
        """
        Обрабатывает неудачную попытку входа, увеличивая счетчик в БД и блокируя при необходимости.
        Эта функция самостоятельно коммитит изменения и выбрасывает исключение.
        """
        # begin_nested защищает от ошибок, если функция вызывается внутри другой транзакции.
        async with db.begin_nested():
            user.registration_attempts += 1
            attempts_left = settings.auth.registration_max_attempts - user.registration_attempts

            if attempts_left <= 0:
                user.status = UserStatus.BLOCKED
                user.registration_attempts = 0

        if attempts_left <= 0:
            logger.warning(f"Пользователь {user} заблокирован из-за превышения попыток входа.")
            raise exceptions.AttemptsLimitExceededError(
                "Превышено количество попыток. Ваша учетная запись заблокирована."
            )

        logger.info(f"Неудачная попытка входа для {user}. Осталось попыток: {attempts_left}")
        raise exceptions.InvalidCredentialsError(f"Неверный код. Осталось попыток: {attempts_left}")

    @staticmethod
    async def _clear_login_attempts(user: User) -> None:
        """
        Очищает счетчик попыток входа и блокировку для пользователя.
        Эта функция только изменяет состояние объекта, коммит должен быть снаружи.
        """
        user.registration_attempts = 0

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
        async with db.begin_nested():
            new_guest_user = User(telegram_id=telegram_id, role=UserRole.GUEST)
            db.add(new_guest_user)
            try:
                await db.flush()
                await db.refresh(new_guest_user)
                logger.info(
                    f"Создан новый ГОСТЬ с ID={new_guest_user.id} для telegram_id={telegram_id}"
                )
                return new_guest_user
            except IntegrityError:
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
    async def _consume_registration_code(
        db: AsyncSession, code: str, user_id: int
    ) -> UserRole | None:
        """
        Помечает код регистрации как использованный и возвращает роль.
        Возвращает None, если код не найден или уже использован.
        """
        res = await db.execute(
            update(RegistrationCode)
            .where(RegistrationCode.code == code, RegistrationCode.is_used.is_(False))
            .values(is_used=True, used_by_user_id=user_id)
            .returning(RegistrationCode.role_type)
        )
        row = res.first()
        return row[0] if row else None

    @staticmethod
    async def auth_by_code(
        db: AsyncSession,
        telegram_id: int,
        username: str,
        code: str,
    ) -> AuthSuccessResponse:
        """
        Обрабатывает регистрацию/аутентификацию пользователя по коду приглашения.
        Вся логика выполняется в одной атомарной транзакции для обеспечения консистентности данных.
        """
        AuthService._validate_input_data(telegram_id, code)
        masked_code = AuthService._mask_sensitive_data(code)
        logger.info(f"Попытка аутентификации {telegram_id} с кодом {masked_code}")

        try:
            user_to_return = None
            async with db.begin():
                user = await AuthService._find_existing_user(db, telegram_id)

                if user and user.role is not None:
                    if AuthService._is_user_locked(user):
                        raise exceptions.AccountLockedError("Превышено количество попыток.")

                    logger.info(
                        f"Пользователь {telegram_id} уже зарегистрирован. Возвращаем существующие данные."
                    )
                    access_token = AuthService.create_access_token(user)
                    return AuthSuccessResponse(
                        user=UserInfo(id=user.id, role=user.role.value),
                        access_token=access_token,
                        already_registered=True,
                    )

                is_new_user = not user

                if is_new_user:
                    logger.info(
                        f"Пользователь с telegram_id={telegram_id} не найден. Создание нового."
                    )
                    user = User(telegram_id=telegram_id)
                    db.add(user)
                    await db.flush()

                role = await AuthService._consume_registration_code(db, code, user.id)

                if not role:
                    if is_new_user:
                        logger.warning(
                            f"Новый пользователь {telegram_id} ввел неверный код {masked_code}."
                        )
                        raise exceptions.InvalidCredentialsError("Неверный код регистрации.")

                    else:
                        await AuthService._handle_failed_attempt(db, user)

                logger.info(
                    f"Код {masked_code} принят для пользователя {user}. Присвоена роль {role}."
                )
                user.username = username
                user.role = role
                user.status = UserStatus.ACTIVE
                await AuthService._clear_login_attempts(user)

                user_to_return = user

            await db.refresh(user_to_return)

            role_name = getattr(user_to_return.role, "value", str(user_to_return.role))
            logger.info(
                f"Пользователь {user_to_return} успешно аутентифицирован с ролью {role_name}"
            )

            access_token = AuthService.create_access_token(user_to_return)
            return AuthSuccessResponse(
                user=UserInfo(id=user_to_return.id, role=role_name),
                access_token=access_token,
                already_registered=False,
            )

        except (
            exceptions.InvalidCredentialsError,
            exceptions.AttemptsLimitExceededError,
            exceptions.AccountLockedError,
            exceptions.UserAlreadyRegisteredError,
        ):
            raise
        except Exception:
            logger.exception(f"Непредвиденная ошибка при аутентификации {telegram_id}")
            raise exceptions.AuthError("Произошла внутренняя ошибка при аутентификации.")


# Вспомогательные функции для обратной совместимости
def create_access_token(user: User) -> str:
    """Создает новый JWT токен (функция для обратной совместимости)."""
    return AuthService.create_access_token(user)


async def get_user_by_telegram_id_or_create_guest(telegram_id: int, db: AsyncSession) -> User:
    """Находит или создает пользователя-гостя (функция для обратной совместимости)."""
    return await AuthService.get_user_by_telegram_id_or_create_guest(telegram_id, db)
