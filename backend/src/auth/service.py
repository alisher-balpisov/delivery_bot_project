import redis.asyncio as aioredis
from backend.src.common.enums import UserRole
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def auth_by_code(db: AsyncSession, redis: aioredis.Redis, telegram_id: int, code: str):
    """
    Обрабатывает регистрацию пользователя по коду приглашения,
    используя Redis для отслеживания попыток и временной блокировки.
    """

    # 1. Проверка, не зарегистрирован ли пользователь уже
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user and user.role not in [UserRole.PENDING, UserRole.GUEST]:
        logger.info(f"Пользователь {telegram_id} уже зарегистрирован с ролью {user.role.value}.")
        return {
            "success": True,
            "already_registered": True,
            "user": {"id": user.id, "role": user.role.value},
        }

    # 2. Проверка временной блокировки в Redis
    lock_key = f"login_lock:{telegram_id}"
    if await redis.exists(lock_key):
        ttl = await redis.ttl(lock_key)
        logger.warning(
            f"Попытка регистрации от заблокированного пользователя {telegram_id}. Блокировка на {ttl} сек."
        )
        return {
            "success": False,
            "blocked": True,
            "detail": f"Превышено количество попыток. Попробуйте снова через {ttl // 60 + 1} минут.",
        }

    # 3. Поиск кода регистрации в БД
    registration_code = await db.scalar(
        select(RegistrationCode).where(
            RegistrationCode.code == code, RegistrationCode.is_used.is_(False)
        )
    )

    # 4. Обработка ПРАВИЛЬНОГО кода
    if registration_code:
        logger.info(
            f"Для пользователя {telegram_id} найден валидный код: {code}, роль: {registration_code.role.value}."
        )

        # Если пользователя не было, создаем
        if not user:
            user = User(telegram_id=telegram_id)
            db.add(user)
            await db.flush()  # Получаем user.id до коммита

        # Обновляем данные пользователя
        user.role = registration_code.role
        user.is_blocked = False  # Снимаем возможную ручную блокировку

        # Обновляем данные кода
        registration_code.is_used = True
        registration_code.user_id = user.id

        await db.commit()
        logger.info(
            f"Пользователь {telegram_id} успешно зарегистрирован. Код {code} помечен как использованный."
        )

        # Удаляем ключ с попытками из Redis при успехе
        attempts_key = f"login_attempts:{telegram_id}"
        await redis.delete(attempts_key)

        return {"success": True, "user": {"id": user.id, "role": user.role.value}}

    # 5. Обработка НЕПРАВИЛЬНОГО кода
    else:
        logger.warning(f"Пользователь {telegram_id} ввел неверный/использованный код: {code}.")
        attempts_key = f"login_attempts:{telegram_id}"

        current_attempts = await redis.incr(attempts_key)

        # Если это первая попытка, устанавливаем TTL
        if current_attempts == 1:
            await redis.expire(attempts_key, settings.redis.default_ttl_seconds)

        attempts_left = settings.business.registration_max_attempts - current_attempts

        if attempts_left > 0:
            logger.info(f"У пользователя {telegram_id} осталось {attempts_left} попыток.")
            return {"success": False, "attempts_left": attempts_left}
        else:
            # Блокируем пользователя
            logger.warning(
                f"Пользователь {telegram_id} заблокирован из-за превышения попыток ввода кода."
            )
            await redis.set(lock_key, "locked", ex=settings.redis.default_ttl_seconds)
            await redis.delete(attempts_key)  # Удаляем счетчик, т.к. теперь есть ключ блокировки
            return {
                "success": False,
                "blocked": True,
                "detail": f"Превышено количество попыток. Попробуйте снова через {settings.redis.default_ttl_seconds // 60} минут.",
            }
