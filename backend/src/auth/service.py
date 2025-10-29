from datetime import UTC, datetime, timedelta

from backend.src.auth import exceptions
from backend.src.common.constants import MAX_CODE_LENGTH
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
            .returning(RegistrationCode.role)
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
        """Регистрация/аутентификация пользователя по коду приглашения."""
        AuthService._validate_input_data(telegram_id, code)
        masked_code = AuthService._mask_sensitive_data(code)
        logger.info(f"Попытка аутентификации {telegram_id} с кодом {masked_code}")

        try:
            async with db.begin():
                """Проверяем существование пользователя"""
                user = await AuthService._get_or_create_user(db, telegram_id)

                """Проверяем, не зарегистрирован ли уже"""
                if AuthService._is_already_registered(user):
                    return await AuthService._handle_already_registered(user)

                """Пробуем применить код"""
                role = await AuthService._try_consume_code(db, user, code, masked_code)

                """Успешное присвоение роли"""
                await AuthService._activate_user(user, username, role)

            """После транзакции: обновляем и возвращаем токен"""
            await db.refresh(user)
            return await AuthService._finalize_auth(user)

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

    @staticmethod
    async def _get_or_create_user(db: AsyncSession, telegram_id: int) -> User:
        user = await AuthService._find_existing_user(db, telegram_id)
        if not user:
            user = User(telegram_id=telegram_id)
            db.add(user)
            await db.flush()
            logger.info(f"Создан новый пользователь с telegram_id={telegram_id}")
        return user

    @staticmethod
    def _is_already_registered(user: User) -> bool:
        return user.role is not None

    @staticmethod
    async def _handle_already_registered(user: User) -> AuthSuccessResponse:
        if AuthService._is_user_locked(user):
            raise exceptions.AccountLockedError("Превышено количество попыток.")
        token = AuthService.create_access_token(user)
        logger.info(f"Пользователь {user.telegram_id} уже зарегистрирован.")
        return AuthSuccessResponse(
            user=UserInfo(id=user.id, role=user.role.value),
            access_token=token,
            already_registered=True,
        )

    @staticmethod
    async def _try_consume_code(
        db: AsyncSession, user: User, code: str, masked_code: str
    ) -> UserRole:
        role = await AuthService._consume_registration_code(db, code, user.id)
        if not role:
            logger.warning(f"Пользователь {user.telegram_id} ввел неверный код {masked_code}")
            await AuthService._handle_failed_attempt(db, user)
        return role

    @staticmethod
    async def _activate_user(user: User, username: str, role: UserRole) -> None:
        user.username = username
        user.role = role
        user.status = UserStatus.ACTIVE
        await AuthService._clear_login_attempts(user)

    @staticmethod
    async def _finalize_auth(user: User) -> AuthSuccessResponse:
        role_name = getattr(user.role, "value", str(user.role))
        logger.info(f"Пользователь {user.telegram_id} успешно аутентифицирован с ролью {role_name}")
        token = AuthService.create_access_token(user)
        return AuthSuccessResponse(
            user=UserInfo(id=user.id, role=role_name),
            access_token=token,
            already_registered=False,
        )
