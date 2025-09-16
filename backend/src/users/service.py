from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.shop import Shop
from backend.src.models.user import User
from backend.src.schemas.admin import CodeActivationResponse
from backend.src.schemas.courier import CourierResponse
from backend.src.schemas.user import UserCreateWithoutPassword, UserResponse, UserUpdate
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

MAX_ATTEMPTS = 3

logger = get_logger(__name__)


def _validate_activation_request(code: str) -> str:
    """Валидирует входные данные для активации."""
    if not code or not code.strip():
        raise HTTPException(status_code=400, detail="Код не может быть пустым")
    return code.strip()


async def _check_user_activation_status(
    db: AsyncSession, telegram_id: int
) -> CodeActivationResponse | None:
    """Проверяет статус активации пользователя."""
    logger.debug(f"Calling _get_existing_user with telegram_id={telegram_id}")
    existing_user = await _get_existing_user(db, telegram_id)
    logger.debug(f"_get_existing_user returned: {existing_user}")
    logger.debug(f"Calling _is_user_already_activated with user={existing_user}")
    is_activated = _is_user_already_activated(existing_user)
    logger.debug(f"_is_user_already_activated returned: {is_activated}")
    if is_activated:
        response = CodeActivationResponse(
            success=True, user_id=existing_user.id, role=existing_user.role.value
        )
        logger.debug(f"Returning activation response for already activated user: {response}")
        return response
    logger.debug("_check_user_activation_status returning None")
    return None


async def _process_activation(
    db: AsyncSession,
    existing_user: User | None,
    telegram_id: int,
    code: str,
    requested_role: UserRole | None = None,
) -> CodeActivationResponse:
    """Обрабатывает логику активации кода."""
    logger.debug(f"Calling _find_valid_registration_code with code='{code}'")
    reg_code_obj = await _find_valid_registration_code(db, code)
    logger.debug(f"_find_valid_registration_code returned: {reg_code_obj}")
    if not reg_code_obj:
        logger.info(f"Processing invalid code '{code}' for telegram_id {telegram_id}")
        logger.debug(
            f"Calling _handle_invalid_code with db, existing_user={existing_user}, telegram_id={telegram_id}"
        )
        result = await _handle_invalid_code(db, existing_user, telegram_id)
        logger.debug(f"_handle_invalid_code returned: {result}")
        return result

    logger.debug(
        f"Calling _handle_valid_code with reg_code_obj={reg_code_obj}, requested_role={requested_role}"
    )
    result = await _handle_valid_code(db, existing_user, reg_code_obj, telegram_id, requested_role)
    logger.debug(f"_handle_valid_code returned: {result}")
    return result


async def activate_code(
    db: AsyncSession, telegram_id: int, code: str, requested_role: UserRole | None = None
) -> CodeActivationResponse:
    """
    Проверяет код активации, регистрирует или блокирует пользователя.
    Улучшения: транзакции, разбиение на методы, обработка ошибок.
    """
    logger.debug(
        f"Starting activate_code with telegram_id={telegram_id}, code='{code}', requested_role={requested_role}"
    )

    try:
        logger.debug(f"Calling _validate_activation_request with code='{code}'")
        code = _validate_activation_request(code)
        logger.debug(f"_validate_activation_request returned code='{code}'")

        logger.info(f"Starting activation for telegram_id {telegram_id} with code '{code}'")
        async with db.begin():  # Транзакция для атомарности
            logger.debug(f"Calling _get_existing_user with telegram_id={telegram_id}")
            existing_user = await _get_existing_user(db, telegram_id)
            logger.debug(f"_get_existing_user returned: {existing_user}")
            is_activated = _is_user_already_activated(existing_user)
            logger.debug(f"_is_user_already_activated returned: {is_activated}")

            existing_activation_response = None
            if is_activated:
                existing_activation_response = CodeActivationResponse(
                    success=True, user_id=existing_user.id, role=existing_user.role.value
                )

            logger.debug(f"Calling _find_valid_registration_code with code='{code}'")
            reg_code_obj = await _find_valid_registration_code(db, code)
            logger.debug(f"_find_valid_registration_code returned: {reg_code_obj}")

            if not reg_code_obj:
                logger.info(f"Processing invalid code '{code}' for telegram_id {telegram_id}")
                return await _handle_invalid_code(db, existing_user, telegram_id)

            if reg_code_obj.is_used:
                raise ValueError("Код регистрации уже был активирован")

            if existing_activation_response and reg_code_obj.role != UserRole.ADMIN:
                logger.info(
                    f"User {telegram_id} is already activated, and code not for admin upgrade"
                )
                return existing_activation_response

            logger.debug("Calling _handle_valid_code directly")
            result = await _handle_valid_code(
                db, existing_user, reg_code_obj, telegram_id, requested_role
            )
            logger.debug(f"_process_activation returned: {result}")
            if result.success:
                logger.info(f"Activation successful for telegram_id {telegram_id}")
            else:
                logger.warning(f"Activation failed for telegram_id {telegram_id}: {result}")
            return result
    except HTTPException:
        # Re-raise HTTP exceptions as they are intended responses
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during activation for telegram_id {telegram_id}: {e!s}",
            exc_info=True,
        )
        await db.rollback()  # Откат при ошибке
        raise HTTPException(status_code=500, detail=f"Unexpected error during activation: {e!s}")


async def _get_existing_user(db: AsyncSession, telegram_id: int) -> User | None:
    """Получить существующего пользователя по telegram_id."""
    logger.debug(f"Executing select User where telegram_id={telegram_id}")
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalars().first()
    logger.debug(f"_get_existing_user query result: {user}")
    return user


def _is_user_already_activated(user: User | None) -> bool:
    """Проверить, активирован ли пользователь."""
    return (
        user is not None
        and user.role is not None
        and user.role != UserRole.PENDING
        and user.is_active
        and not user.is_blocked
    )


MAX_CODE_LENGTH = 20  # Синхронизировано с моделью DB


async def _find_valid_registration_code(
    db: AsyncSession, code: str | None
) -> RegistrationCode | None:
    """
    Найти валидный код регистрации (неиспользованный).

    Выполняет валидацию входного кода, нормализацию и поиск с блокировкой
    для предотвращения race conditions. Обрабатывает DB-эксепшены грациозно.
    """
    logger.debug(f"_find_valid_registration_code called with code='{code}'")
    if code is None or not isinstance(code, str):
        logger.warning("Input code is None or not a string")
        return None

    try:
        # Валидация и нормализация через pydantic
        normalized_code = code.strip()

        logger.debug(f"Searching for valid registration code: '{normalized_code}'")

        # Оптимизированный запрос с существующим индексом на code
        # Рекомендация: добавить композитный индекс (code, is_used) для лучшей производительности
        reg_code = await db.scalar(
            select(RegistrationCode)
            .where(
                RegistrationCode.code == normalized_code,
                RegistrationCode.is_used.is_(False),
            )
            .with_for_update()  # Блокировка для предотвращения race conditions
        )

        if reg_code:
            logger.info(
                f"Found valid registration code '{normalized_code}' for role {reg_code.role}"
            )
        else:
            logger.warning(f"Registration code '{normalized_code}' not found or already used")

        return reg_code

    except ValueError as e:
        # Обработка валидационных ошибок (пустой или слишком длинный код)
        logger.warning(f"Validation error for code: {e}")
        return None
    except IntegrityError as e:
        # Конфликт при одновременном использовании кода
        logger.error(f"Integrity error while searching for registration code '{code}': {e}")
        await db.rollback()  # Откат транзакции
        logger.debug("IntegrityError handled gracefully")
        return None
    except OperationalError as e:
        # Сбои подключения к БД
        logger.error(f"DB operational error while searching for registration code '{code}': {e}")
        await db.rollback()
        logger.debug("OperationalError handled gracefully")
        return None
    except SQLAlchemyError as e:
        # Другие ошибки SQLAlchemy
        logger.error(
            f"SQLAlchemy error while searching for registration code '{code}': {e}", exc_info=True
        )
        await db.rollback()
        logger.debug("SQLAlchemyError re-raising for higher level handling")
        raise  # Повторно поднимаем для обработки на уровне выше (например, в транзакции)
    except Exception as e:
        # Непреявиденные ошибки
        logger.error(
            f"Unexpected error while searching for registration code '{code}': {e}", exc_info=True
        )
        await db.rollback()
        logger.debug("Unexpected error re-raising")
        raise


async def _handle_invalid_code(
    db: AsyncSession, existing_user: User | None, telegram_id: int
) -> CodeActivationResponse:
    """Обработать случай неверного кода: увеличить счетчик попыток, заблокировать при необходимости."""
    logger.debug(
        f"_handle_invalid_code called with existing_user={existing_user}, telegram_id={telegram_id}"
    )
    user_to_track = existing_user or User(
        telegram_id=telegram_id, role=UserRole.PENDING, registration_attempts=0
    )
    logger.debug(f"user_to_track: {user_to_track}")

    if user_to_track.is_blocked:
        return CodeActivationResponse(success=False, blocked=True)

    user_to_track.registration_attempts += 1
    attempts_left = MAX_ATTEMPTS - user_to_track.registration_attempts

    if attempts_left <= 0:
        user_to_track.is_blocked = True
        await db.commit()  # Немедленный коммит блокировки
        return CodeActivationResponse(
            success=False, blocked=True, attempts_left=0, detail="Превышено количество попыток"
        )
    else:
        # Если пользователь не существует, не создаем сразу с pending ролью,
        # чтобы избежать ошибок валидации enum в БД
        if not existing_user:
            # Не создаем нового пользователя при неверном коде
            pass
        # Для существующего пользователя, updates are auto-flushed

        await db.commit()  # Зафиксировать изменения attempts

    return CodeActivationResponse(
        success=False,
        blocked=False,
        attempts_left=attempts_left,
        detail="Неверный код",
    )


async def _handle_valid_code(
    db: AsyncSession,
    existing_user: User | None,
    reg_code_obj: RegistrationCode,
    telegram_id: int,
    requested_role: UserRole | None = None,
) -> CodeActivationResponse:
    """Обработать случай верного кода: активировать пользователя и отметить код как использованный."""
    logger.debug(
        f"_handle_valid_code called with existing_user={existing_user}, reg_code_obj={reg_code_obj}, telegram_id={telegram_id}, requested_role={requested_role}"
    )

    # Предотвращение использования кода другим пользователем
    if reg_code_obj.user_id is not None:
        logger.debug(f"reg_code_obj.user_id is not None: {reg_code_obj.user_id}")
        if existing_user and reg_code_obj.user_id != existing_user.id:
            logger.warning(
                f"Code used by different user: reg_code.user_id={reg_code_obj.user_id}, existing_user.id={existing_user.id}"
            )
            raise HTTPException(status_code=409, detail="Код уже использован другим пользователем")
        elif not existing_user:
            logger.warning("Code used but no existing user")
            raise HTTPException(status_code=409, detail="Код уже использован другим пользователем")

    # Проверка совпадения запрошенной роли с ролью кода (если роль указана)
    if requested_role and requested_role != reg_code_obj.role:
        raise HTTPException(
            status_code=400, detail="Запрошенная роль не соответствует роли кода активации"
        )

    user = existing_user or User(
        telegram_id=telegram_id, role=reg_code_obj.role, is_blocked=False, registration_attempts=0
    )

    if not existing_user:
        db.add(user)
        await db.flush()  # Get user.id

    user.role = reg_code_obj.role
    user.is_blocked = False
    user.registration_attempts = 0
    user.registration_code_id = reg_code_obj.id

    reg_code_obj.is_used = True
    reg_code_obj.user_id = user.id

    # Убедимся, что изменения сохранены (хотя begin должен сделать это)
    logger.debug("Committing changes to DB")
    await db.commit()
    await db.refresh(user)
    await db.refresh(reg_code_obj)
    logger.debug("DB commit completed, returning successful response")
    response = CodeActivationResponse(success=True, user_id=user.id, role=user.role.value)
    logger.debug(f"Returning response: {response}")
    return response


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
    """
    Поиск пользователя по Telegram ID.
    Проверяет активность и блокировку пользователя.
    """
    try:
        logger.debug(f"Searching user by telegram_id: {telegram_id}")
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if user:
            logger.debug(
                f"User found: id={user.id}, telegram_id={user.telegram_id}, role={user.role}, active={user.is_active}, blocked={user.is_blocked}"
            )
            if user.is_blocked:
                logger.warning(f"User {telegram_id} is blocked")
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            if not user.is_active:
                logger.warning(f"User {telegram_id} is not active")
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            return user
        else:
            logger.info(f"User with telegram_id {telegram_id} not found")
            return None
    except Exception as e:
        logger.error(f"Error getting user by telegram_id {telegram_id}: {e}", exc_info=True)
        raise


async def get_user_response_by_telegram_id(
    db: AsyncSession, telegram_id: int
) -> UserResponse | None:
    """
    Поиск пользователя по Telegram ID с возвратом Pydantic модели.
    """
    user = await get_user_by_telegram_id(db, telegram_id)
    if user:
        try:
            return UserResponse.model_validate(user)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка валидации пользователя: {e!s}")
    return None


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


async def get_all_couriers(db: AsyncSession) -> list[CourierResponse]:
    """
    Получение списка всех активных курьеров (для администраторов).
    """
    result = await db.execute(select(Courier).join(User))
    couriers = result.scalars().all()
    return [CourierResponse.model_validate(cour) for cour in couriers]


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
    if user.role == UserRole.SHOP:
        shop = Shop(user_id=user.id, name="", address="")
        db.add(shop)
    elif user.role == UserRole.COURIER:
        courier = Courier(user_id=user.id)
        db.add(courier)

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
