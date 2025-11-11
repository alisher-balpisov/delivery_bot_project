from datetime import UTC, datetime, timedelta

from backend.src.auth.schemas import AuthSuccessResponse, UserInfo
from backend.src.common.enums import TokenType, UserRole, UserStatus
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.shop import Shop
from backend.src.models.user import User
from fastapi import HTTPException, status
from icecream import ic
from jose import JWTError, jwt
from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import exceptions

logger = get_logger(__name__)


def create_access_token(user: User) -> str:
    """
    Создаёт access JWT токен для пользователя.
    Короткий срок действия (15 минут).
    """
    if not user or not user.id:
        raise ValueError("Пользователь должен иметь валидный ID")

    if user.role == UserRole.GUEST:
        logger.warning(f"Пользователю {user} с ролью GUEST был отказано в доступе")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа.",
        )

    to_encode: dict[str, str | int] = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": TokenType.ACCESS,
        "iat": int(datetime.now(UTC).timestamp()),
        "tid": str(user.telegram_id),
    }

    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt.access_token_expire_minutes)
    to_encode["exp"] = int(expire.timestamp())

    try:
        return jwt.encode(
            to_encode,
            settings.jwt.secret_key.get_secret_value(),
            algorithm=settings.jwt.algorithm,
        )
    except Exception as e:
        logger.exception(f"Ошибка при создании JWT токена для пользователя {user}")
        raise JWTError(f"Не удалось создать токен: {e}")


def create_refresh_token(user: User) -> str:
    """
    Создаёт refresh JWT токен для пользователя.
    Длительный срок действия (30 дней).

    Содержит минимум информации для безопасности.
    """
    if not user or not user.id:
        raise ValueError("Пользователь должен иметь валидный ID")

    to_encode: dict[str, str | int] = {
        "sub": str(user.id),
        "type": TokenType.REFRESH,
        "iat": int(datetime.now(UTC).timestamp()),
    }

    expire = datetime.now(UTC) + timedelta(days=settings.jwt.refresh_token_expire_days)
    to_encode["exp"] = int(expire.timestamp())

    try:
        # Используем отдельный секрет для refresh токенов (если настроен)
        secret = settings.jwt.refresh_secret

        return jwt.encode(
            to_encode,
            secret,
            algorithm=settings.jwt.algorithm,
        )
    except Exception as e:
        logger.exception(f"Ошибка при создании refresh токена для пользователя {user}")
        raise JWTError(f"Не удалось создать refresh токен: {e}")


def create_token_pair(user: User) -> tuple[str, str]:
    """
    Создаёт пару токенов: access + refresh.

    Returns:
        (access_token, refresh_token)
    """
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    logger.info(f"Создана пара токенов для пользователя {user.id}")

    return access_token, refresh_token


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
) -> tuple[str, str]:
    """
    Обновляет access token используя refresh token.

    Args:
        db: Сессия БД
        refresh_token: Существующий refresh token (JWT)

    Returns:
        (new_access_token, new_refresh_token)

    Raises:
        exceptions.InvalidRefreshTokenError: Если токен невалиден
    """
    try:
        # 1. Декодируем refresh token
        secret = settings.jwt.refresh_secret
        payload = jwt.decode(
            refresh_token,
            secret,
            algorithms=[settings.jwt.algorithm],
        )

        # 2. Проверяем тип токена
        token_type = payload.get("type")
        if token_type != TokenType.REFRESH:
            logger.warning("Попытка использовать не-refresh токен для обновления")
            raise exceptions.InvalidRefreshTokenError(
                "Невалидный тип токена. Ожидается refresh token."
            )

        # 3. Извлекаем user_id
        sub = payload.get("sub")
        if sub is None:
            logger.warning("В refresh токене отсутствует 'sub'")
            raise exceptions.InvalidRefreshTokenError("Невалидный refresh token")

        try:
            user_id = int(sub)
        except (TypeError, ValueError):
            raise exceptions.InvalidRefreshTokenError("Невалидный ID пользователя в токене")

    except JWTError as e:
        logger.warning(f"Ошибка декодирования refresh токена: {e}")
        raise exceptions.InvalidRefreshTokenError("Refresh token невалиден или истёк")

    # 4. Загружаем пользователя из БД
    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"Пользователь {user_id} из refresh токена не найден в БД")
        raise exceptions.InvalidRefreshTokenError("Пользователь не найден")

    # 5. Проверяем статус пользователя
    if user.status == UserStatus.BLOCKED:
        logger.warning(f"Заблокированный пользователь {user.id} попытался обновить токен")
        raise exceptions.AccountLockedError("Учетная запись заблокирована")

    if user.status == UserStatus.INACTIVE:
        logger.warning(f"Неактивный пользователь {user.id} попытался обновить токен")
        raise exceptions.AccountInactiveError("Учетная запись неактивна")

    if user.role == UserRole.GUEST:
        logger.warning(f"Пользователь {user.id} с ролью GUEST попытался обновить токен")
        raise exceptions.InvalidRefreshTokenError("Недостаточно прав доступа")

    # 6. Создаём новую пару токенов
    new_access_token, new_refresh_token = create_token_pair(user)

    logger.info(f"Токены обновлены для пользователя {user.id}")

    return new_access_token, new_refresh_token


def _validate_input_data(username: str | None, telegram_id: int, code: str) -> None:
    """Валидирует входные данные."""

    _validate_username(username)

    if not code.strip() or len(code) != settings.auth.code_length:
        raise ValueError("Некорректный код регистрации")


def mask_sensitive_data(code: str) -> str:
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
        await db.flush()

        attempts_left = settings.auth.registration_max_attempts - user.registration_attempts

        if attempts_left <= 0:
            user.status = UserStatus.BLOCKED
            user.registration_attempts = 0
            await db.flush()

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


def _validate_username(username: str | None) -> str | None:
    if username is None:
        return None

    username = username.strip()

    if len(username) > 64:
        raise ValueError("Username слишком длинный")

    if not username.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Username содержит недопустимые символы")

    return username


async def _consume_registration_code(db: AsyncSession, code: str, user_id: int) -> UserRole | None:
    """
    Помечает код регистрации как использованный и возвращает роль.
    Возвращает None, если код не найден или уже использован.
    """
    res = await db.execute(
        update(RegistrationCode)
        .where(
            RegistrationCode.code == code,
            RegistrationCode.is_used.is_(False),
            RegistrationCode.expires_at > datetime.now(UTC),
        )
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
        ic(user)
        db.add(user)
        await db.flush()
        logger.info(f"Создан новый пользователь с telegram_id={telegram_id}")
    return user


def _is_already_registered(user: User) -> bool:
    """Проверяет, была ли пользователю уже присвоена роль."""
    return user.role != UserRole.GUEST


async def _handle_already_registered(user: User) -> AuthSuccessResponse:
    """Обрабатывает случай, когда пользователь уже зарегистрирован."""

    if user.role == UserRole.GUEST:
        raise exceptions.AuthError("Недопустимый статус пользователя")
    if _is_user_locked(user):
        raise exceptions.AccountLockedError("Учетная запись заблокирована.")

    access_token, refresh_token = create_token_pair(user)

    logger.info(f"Пользователь {user} уже зарегистрирован. Выдана новая пара токенов.")
    return AuthSuccessResponse(
        user=UserInfo(id=user.id, role=user.role.value),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt.access_token_expire_minutes * 60,
        refresh_expires_in=settings.jwt.refresh_token_expire_days * 24 * 60 * 60,
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


async def _create_profile_if_needed(db: AsyncSession, user: User) -> None:
    """Создает профиль магазина или курьера, если он отсутствует."""
    if user.role == UserRole.SHOP:
        has_shop = await db.scalar(select(exists().where(Shop.user_id == user.id)))
        if not has_shop:
            db.add(Shop(user_id=user.id))
            logger.info("Создан профиль магазина для пользователя %s", user.id)
    elif user.role == UserRole.COURIER:
        has_courier = await db.scalar(select(Courier).where(Courier.user_id == user.id))
        if not has_courier:
            db.add(Courier(user_id=user.id))
            logger.info("Создан профиль курьера для пользователя %s", user.id)


async def _finalize_auth(user: User) -> AuthSuccessResponse:
    """Завершает процесс аутентификации, создавая пару токенов и ответ."""
    role_name = getattr(user.role, "value", str(user.role))
    logger.info(f"Пользователь {user} успешно аутентифицирован с ролью {role_name}")

    access_token, refresh_token = create_token_pair(user)

    return AuthSuccessResponse(
        user=UserInfo(id=user.id, role=role_name),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt.access_token_expire_minutes * 60,  # в секундах
        refresh_expires_in=settings.jwt.refresh_token_expire_days * 24 * 60 * 60,  # в секундах
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
    _validate_input_data(username, telegram_id, code)
    masked_code = mask_sensitive_data(code)
    logger.info(f"Попытка аутентификации telegram_id={telegram_id} с кодом {masked_code}")

    try:
        async with db.begin():
            ic()
            user = await _get_or_create_user(db, telegram_id)
            ic(user)

            if ic(_is_already_registered(user)):
                if _is_user_locked(user):
                    raise exceptions.AccountLockedError("Учетная запись заблокирована.")
                return await _handle_already_registered(user)

            role = await _try_consume_code(db, user, code, masked_code)

            await _activate_user(user, username, role)
            await _create_profile_if_needed(db, user)
            await db.flush()
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

    Возвращает токены если пользователь зарегистрирован и активен.

    Raises:
        InvalidCredentialsError (401): Пользователь не найден
        RegistrationIncompleteError (403): Регистрация не завершена
        AccountLockedError (423): Аккаунт заблокирован
    """
    logger.info(f"Попытка входа для telegram_id={telegram_id}")

    try:
        user = await _find_existing_user(db, telegram_id)

        # 1. Проверяем, что пользователь вообще существует
        if not user:
            logger.warning(f"Попытка входа для несуществующего telegram_id={telegram_id}")
            raise exceptions.InvalidCredentialsError("Пользователь не найден.")

        # 2. Проверка статуса регистрации
        if user.status == UserStatus.PENDING_REGISTRATION:
            logger.info(f"Пользователь {user} не завершил регистрацию")
            raise exceptions.RegistrationIncompleteError(
                "Регистрация не завершена. Пожалуйста, введите код приглашения."
            )

        # 3. Проверяем блокировку
        if _is_user_locked(user):
            logger.warning(f"Заблокированный пользователь {user} попытался войти")
            raise exceptions.AccountLockedError("Учетная запись заблокирована.")

        # 4. Проверяем неактивность
        if user.status == UserStatus.INACTIVE:
            logger.warning(f"Неактивный пользователь {user} попытался войти")
            raise exceptions.AccountInactiveError("Учетная запись неактивна.")

        # 5. Проверяем, что у пользователя есть роль (дополнительная проверка)
        if not _is_already_registered(user):
            logger.error(f"Пользователь {user} имеет статус {user.status}, но роль GUEST")
            raise exceptions.InvalidCredentialsError(
                "Данные пользователя повреждены. Обратитесь в поддержку."
            )

        # 6. Если все проверки пройдены, создаём и возвращаем токен
        await _clear_login_attempts(user)
        await db.commit()

        logger.info(f"Пользователь {user} успешно вошёл в систему.")
        return await _handle_already_registered(user)

    except (
        exceptions.InvalidCredentialsError,
        exceptions.AccountLockedError,
        exceptions.RegistrationIncompleteError,
        exceptions.AccountInactiveError,
    ):
        raise
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при входе telegram_id={telegram_id}")
        raise exceptions.AuthError("Произошла внутренняя ошибка при аутентификации.") from e
