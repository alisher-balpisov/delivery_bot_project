from datetime import UTC, datetime, timedelta

from backend.src.auth import exceptions
from backend.src.common.enums import UserRole, UserStatus
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.user import User
from backend.src.schemas.auth import AuthSuccessResponse, UserInfo
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


def create_access_token(user: User) -> str:
    """
    Создает новый JWT токен для пользователя.

    Args:
        user: Пользователь, для которого создается токен

    Returns:
        JWT токен в виде строки

    Raises:
        ValueError: Если у пользователя нет ID.
        HTTPException: Если у пользователя нет роли.
        JWTError: Если произошла ошибка при создании токена.
    """
    if not user or not user.id:
        raise ValueError("Пользователь должен иметь валидный ID")

    if user.role == UserRole.GUEST:
        logger.warning(f"Пользователю {user} с ролью GUEST был отказано в доступе")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа.",
        )

    to_encode = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": datetime.now(UTC),
        "tid": str(user.telegram_id),
    }

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


def _validate_input_data(telegram_id: int, code: str) -> None:
    """Валидирует входные данные."""
    _validate_telegram_id(telegram_id)
    ic(
        telegram_id,
        code,
        not isinstance(code, str),
        not code.strip(),
        len(code) != settings.auth.code_length,
    )
    if not isinstance(code, str) or not code.strip() or len(code) != settings.auth.code_length:
        raise ValueError("Некорректный код регистрации")


def _mask_sensitive_data(code: str) -> str:
    """Маскирует чувствительные данные для логирования."""
    if len(code) <= 2:
        return "*" * len(code)
    return code[0] + "*" * (len(code) - 2) + code[-1]


def _is_user_locked(user: User) -> bool:
    """Проверяет, заблокирован ли пользователь."""
    return user.status == UserStatus.BLOCKED


async def _handle_failed_attempt(db: AsyncSession, user: User) -> None:
    """
    Обрабатывает неудачную попытку входа, увеличивая счетчик в БД и блокируя при необходимости.
    Эта функция самостоятельно коммитит изменения и всегда выбрасывает исключение.
    """
    async with db.begin_nested():
        user.registration_attempts += 1
        attempts_left = settings.auth.registration_max_attempts - user.registration_attempts

        if attempts_left <= 0:
            user.status = UserStatus.BLOCKED
            user.registration_attempts = 0  # Сбрасываем счетчик после блокировки

    if attempts_left <= 0:
        logger.warning(f"Пользователь {user} заблокирован из-за превышения попыток входа.")
        raise exceptions.AttemptsLimitExceededError(
            "Превышено количество попыток. Ваша учетная запись заблокирована."
        )

    logger.info(f"Неудачная попытка входа для {user}. Осталось попыток: {attempts_left}")
    raise exceptions.InvalidCredentialsError(f"Неверный код. Осталось попыток: {attempts_left}")


async def _clear_login_attempts(user: User) -> None:
    """
    Очищает счетчик попыток входа для пользователя.
    Эта функция только изменяет состояние объекта, коммит должен быть снаружи.
    """
    user.registration_attempts = 0


async def _find_existing_user(db: AsyncSession, telegram_id: int) -> User | None:
    """Ищет существующего пользователя по telegram_id."""
    return await db.scalar(select(User).where(User.telegram_id == telegram_id))


def _validate_telegram_id(telegram_id: int) -> None:
    """Валидирует Telegram ID."""
    if not isinstance(telegram_id, int):
        raise ValueError("Некорректный Telegram ID")


async def _consume_registration_code(db: AsyncSession, code: str, user_id: int) -> UserRole | None:
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
    return row.role if row else None


async def _get_or_create_user(db: AsyncSession, telegram_id: int) -> User:
    """Находит существующего пользователя или создает нового."""
    user = await _find_existing_user(db, telegram_id)
    if not user:
        user = User(telegram_id=telegram_id, status=UserStatus.PENDING_REGISTRATION)
        db.add(user)
        await db.flush()  # Получаем ID пользователя до коммита транзакции
        logger.info(f"Создан новый пользователь с telegram_id={telegram_id}")
    return user


def _is_already_registered(user: User) -> bool:
    """Проверяет, была ли пользователю уже присвоена роль."""
    return user.role != UserRole.GUEST


async def _handle_already_registered(user: User) -> AuthSuccessResponse:
    """Обрабатывает случай, когда пользователь уже зарегистрирован."""
    # ДОБАВЛЕНО: Утверждение для помощи статическому анализатору и для надежности
    assert user.role != UserRole.GUEST, (
        "Эта функция должна быть доступна только зарегистрированным пользователям."
    )

    if _is_user_locked(user):
        raise exceptions.AccountLockedError("Учетная запись заблокирована.")

    token = create_access_token(user)
    logger.info(f"Пользователь {user} уже зарегистрирован. Выдан новый токен.")
    return AuthSuccessResponse(
        user=UserInfo(id=user.id, role=user.role.value),
        access_token=token,
        already_registered=True,
    )


async def _try_consume_code(db: AsyncSession, user: User, code: str, masked_code: str) -> UserRole:
    """Пытается применить код регистрации. В случае неудачи выбрасывает исключение."""
    role = await _consume_registration_code(db, code, user.id)
    if not role:
        logger.warning(f"Пользователь {user} ввел неверный код {masked_code}")
        await _handle_failed_attempt(db, user)
        raise exceptions.InvalidCredentialsError("Неверный код регистрации.")

    return role


async def _activate_user(user: User, username: str | None, role: UserRole) -> None:
    """Активирует пользователя, присваивая ему роль, имя и сбрасывая счетчики попыток."""
    user.username = username
    user.role = role
    user.status = UserStatus.ACTIVE
    await _clear_login_attempts(user)


async def _finalize_auth(user: User) -> AuthSuccessResponse:
    """Завершает процесс аутентификации, создавая токен и ответ."""
    role_name = getattr(user.role, "value", str(user.role))
    logger.info(f"Пользователь {user} успешно аутентифицирован с ролью {role_name}")
    token = create_access_token(user)
    return AuthSuccessResponse(
        user=UserInfo(id=user.id, role=role_name),
        access_token=token,
        already_registered=False,
    )


async def auth_by_code(
    db: AsyncSession,
    telegram_id: int,
    username: str | None,
    code: str,
) -> AuthSuccessResponse:
    """
    Регистрация/аутентификация пользователя по коду приглашения.
    Основная оркестрирующая функция.
    """
    _validate_input_data(telegram_id, code)
    masked_code = _mask_sensitive_data(code)
    logger.info(f"Попытка аутентификации telegram_id={telegram_id} с кодом {masked_code}")

    try:
        async with db.begin():
            user = await _get_or_create_user(db, telegram_id)

            if _is_already_registered(user):
                return await _handle_already_registered(user)

            role = await _try_consume_code(db, user, code, masked_code)

            await _activate_user(user, username, role)

        await db.refresh(user)
        return await _finalize_auth(user)

    except (
        exceptions.InvalidCredentialsError,
        exceptions.AttemptsLimitExceededError,
        exceptions.AccountLockedError,
    ):
        raise
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при аутентификации telegram_id={telegram_id}")
        raise exceptions.AuthError("Произошла внутренняя ошибка при аутентификации.") from e


async def login(db: AsyncSession, telegram_id: int) -> AuthSuccessResponse:
    """
    Аутентификация существующего пользователя по telegram_id.

    Args:
        db: Сессия базы данных.
        telegram_id: ID пользователя в Telegram.

    Returns:
        Ответ с токеном доступа и информацией о пользователе.

    Raises:
        exceptions.InvalidCredentialsError: Если пользователь не найден или не зарегистрирован.
        exceptions.AccountLockedError: Если учетная запись пользователя заблокирована.
        exceptions.AuthError: При других ошибках аутентификации.
    """
    logger.info(f"Попытка входа для telegram_id={telegram_id}")
    _validate_telegram_id(telegram_id)  # Используем существующий валидатор

    try:
        user = await _find_existing_user(db, telegram_id)

        # 1. Проверяем, что пользователь вообще существует
        if not user:
            logger.warning(f"Попытка входа для несуществующего telegram_id={telegram_id}")
            raise exceptions.InvalidCredentialsError("Пользователь не найден.")

        # 3. Проверяем, что пользователь уже прошел регистрацию (имеет роль)
        if not _is_already_registered(user):
            logger.warning(f"Попытка входа для незарегистрированного пользователя {user}")
            raise exceptions.InvalidCredentialsError("Пользователь не завершил регистрацию.")

        # Если все проверки пройдены, создаем и возвращаем токен
        await _clear_login_attempts(user)  # На всякий случай сбросим счетчик неудачных попыток
        await db.commit()

        logger.info(f"Пользователь {user} успешно вошел в систему.")

        return await _handle_already_registered(user)

    except (exceptions.InvalidCredentialsError, exceptions.AccountLockedError):
        # Пробрасываем ожидаемые исключения выше
        raise
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при входе telegram_id={telegram_id}")
        # Оборачиваем непредвиденные ошибки в наше общее исключение AuthError
        raise exceptions.AuthError("Произошла внутренняя ошибка при аутентификации.") from e
