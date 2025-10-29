import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.common.enums import DisputeStatus, OrderStatus, UserRole
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.user import User
from backend.src.schemas.admin import RegistrationCodeResponse

logger = get_logger(__name__)


async def create_registration_code(
    db: AsyncSession, role: UserRole, created_by_admin_id: int
) -> RegistrationCode:
    """
    Генерирует и сохраняет в БД одноразовый код регистрации для пользователя.

    Args:
        db: Сессия базы данных.
        role: Роль, для которой генерируется код (shop или courier).
        created_by_admin_id: ID админа, который создал код.

    Returns:
        Объект RegistrationCode, добавленный в сессию.

    Raises:
        HTTPException: если указана недопустимая роль.
        RuntimeError: если не удалось сгенерировать уникальный код после нескольких попыток.
    """
    logger.info(f"Генерация кода регистрации для роли: {role.value}")

    if role not in [UserRole.SHOP, UserRole.COURIER]:
        raise HTTPException(
            status_code=400, detail="Недопустимая роль. Используйте 'courier' или 'shop'"
        )

    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.auth.registration_code_lifetime_hours)

    # Пытаемся сгенерировать уникальный код несколько раз
    for _ in range(10):
        code = "".join(
            secrets.choice(settings.auth.code_characters) for _ in range(settings.auth.code_length)
        )

        reg_code = RegistrationCode(
            code=code,
            role=role,
            is_used=False,
            created_by_admin_id=created_by_admin_id,
            created_at=now,
            expires_at=expires_at,
        )
        db.add(reg_code)

        try:
            await db.flush()
            await db.refresh(reg_code)

            logger.info(f"Сгенерирован код регистрации '{reg_code.code}' для роли: {role.value}")
            return reg_code
        except IntegrityError:
            logger.warning(f"Коллизия при генерации кода: '{code}'. Повторная попытка.")
            await db.rollback()
            continue

    logger.error("Не удалось сгенерировать уникальный код регистрации после 10 попыток.")
    raise RuntimeError("Не удалось сгенерировать уникальный код регистрации.")


async def get_all_registration_codes(db: AsyncSession) -> list[RegistrationCodeResponse]:
    """
    Получить все коды регистрации (для администраторов).
    """
    result = await db.execute(select(RegistrationCode).order_by(RegistrationCode.created_at.desc()))
    codes = result.scalars().all()
    return [RegistrationCodeResponse.model_validate(code) for code in codes]


async def deactivate_registration_code(db: AsyncSession, code_id: int) -> bool:
    """
    Деактивировать код регистрации (поместить в черный список).

    Returns:
        bool: True если код был найден и деактивирован
    """
    result = await db.execute(select(RegistrationCode).where(RegistrationCode.id == code_id))
    code = result.scalars().first()

    if not code:
        return False

    # Помечаем как использованный
    async with db.begin():
        code.is_used = True

    return True


async def get_registration_codes_by_role(
    db: AsyncSession, role: UserRole
) -> list[RegistrationCodeResponse]:
    """
    Получить все коды регистрации для определенной роли.
    """
    result = await db.execute(
        select(RegistrationCode)
        .where(RegistrationCode.role == role)
        .order_by(RegistrationCode.created_at.desc())
    )
    codes = result.scalars().all()
    return [RegistrationCodeResponse.model_validate(code) for code in codes]


async def get_unused_registration_codes_count(db: AsyncSession) -> dict:
    """
    Получить количество неиспользованных кодов по ролям.
    """
    result = await db.execute(
        select(RegistrationCode.role, func.count())
        .where(RegistrationCode.is_used.is_(False))
        .group_by(RegistrationCode.role)
    )

    counts = dict(result.all())
    return {
        UserRole.SHOP: counts.get(UserRole.SHOP, 0),
        UserRole.COURIER: counts.get(UserRole.COURIER, 0),
        UserRole.ADMIN: counts.get(UserRole.ADMIN, 0),
        "total": sum(counts.values()),
    }


async def get_system_stats(db: AsyncSession) -> dict:
    """
    Получить системную статистику для администраторов.
    Включает счетчики пользователей, заказов и споров.
    """
    # Статистика пользователей по ролям
    user_counts = await db.execute(select(User.role, func.count(User.id)).group_by(User.role))
    users = {role.value: count for role, count in user_counts.all()}
    total_users = sum(users.values())

    # Статистика заказов по статусам
    order_counts = await db.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    )
    orders = {status.value: count for status, count in order_counts.all()}
    total_orders = sum(orders.values())
    completed_orders = orders.get(OrderStatus.COMPLETED.value, 0)
    cancelled_orders = orders.get(OrderStatus.CANCELLED.value, 0)
    active_orders = total_orders - completed_orders - cancelled_orders

    # Статистика споров
    dispute_counts = await db.execute(
        select(Dispute.status, func.count(Dispute.id)).group_by(Dispute.status)
    )
    disputes = {status.value: count for status, count in dispute_counts.all()}
    total_disputes = sum(disputes.values())
    unresolved_disputes = (
        total_disputes
        # - disputes.get(DisputeStatus.CLOSED.value, 0)
        - disputes.get(DisputeStatus.RESOLVED.value, 0)
    )

    return {
        "total_users": total_users,
        "total_admins": users.get(UserRole.ADMIN.value, 0),
        "total_shops": users.get(UserRole.SHOP.value, 0),
        "total_couriers": users.get(UserRole.COURIER.value, 0),
        "total_orders": total_orders,
        "active_orders": active_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "total_disputes": total_disputes,
        "unresolved_disputes": unresolved_disputes,
    }
