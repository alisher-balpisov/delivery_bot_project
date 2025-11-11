import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, load_only, selectinload

from backend.src.auth.service import mask_sensitive_data
from backend.src.common.constants import PaginatedResponse
from backend.src.common.enums import DisputeStatus, OrderStatus, UserRole, UserStatus
from backend.src.common.utils.paginaters import get_paginated_list
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.couriers.schemas import CourierCardResponse
from backend.src.disputes.schemas import DisputeCardResponse
from backend.src.models.courier import Courier
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.shop import Shop
from backend.src.models.user import User
from backend.src.orders.schemas import OrderCardResponse
from backend.src.shops.schemas import ShopCardResponse

from .schemas import RegistrationCodeResponse

logger = get_logger(__name__)

T = TypeVar("T")


# Константы для улучшения читаемости и поддерживаемости
MAX_GENERATION_ATTEMPTS = 10


def _generate_registration_code() -> str:
    """
    Генерирует случайный код регистрации.
    """
    _validate_code_settings()
    code_characters = settings.auth.code_characters
    code_length = settings.auth.code_length
    return "".join(secrets.choice(code_characters) for _ in range(code_length))


def _validate_code_settings() -> None:
    """
    Проверяет корректность настроек для генерации кода.

    Raises:
        ValueError: если настройки некорректны.
    """
    if not settings.auth.code_characters:
        raise ValueError("Набор символов для генерации кода не может быть пустым.")
    if settings.auth.code_length <= 0:
        raise ValueError("Длина кода должна быть положительной.")


def _create_code_object(
    code: str, role: UserRole, created_by_admin_id: int, now: datetime, expires_at: datetime
) -> RegistrationCode:
    """
    Создает объект RegistrationCode с заданными параметрами.
    """
    return RegistrationCode(
        code=code,
        role=role,
        is_used=False,
        created_by_admin_id=created_by_admin_id,
        created_at=now,
        expires_at=expires_at,
    )


async def _try_save_code(db: AsyncSession, reg_code: RegistrationCode, attempt: int) -> bool:
    """
    Пытается сохранить код в БД.

    Args:
        db: Сессия базы данных.
        reg_code: Объект кода для сохранения.
        attempt: Номер текущей попытки.

    Returns:
        True, если код успешно сохранен, False при коллизии.
    """
    db.add(reg_code)
    try:
        await db.flush()
        await db.refresh(reg_code)
        logger.info(
            f"Сгенерирован уникальный код регистрации '{reg_code.code}' "
            f"для роли '{reg_code.role.value}' на попытке {attempt}."
        )
        return True
    except IntegrityError:
        masked_code = mask_sensitive_data(reg_code.code)
        logger.warning(
            f"Коллизия при генерации кода '{masked_code}' на попытке {attempt}. "
            f"Генерируем новый код."
        )
        await db.rollback()
        return False


def _calculate_expiration_time() -> tuple[datetime, datetime]:
    """
    Вычисляет время создания и истечения кода.

    Returns:
        Кортеж (created_at, expires_at).
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.auth.registration_code_lifetime_hours)
    return now, expires_at


async def create_registration_code(
    db: AsyncSession, role: UserRole, created_by_admin_id: int
) -> RegistrationCode:
    """
    Генерирует и сохраняет в БД одноразовый код регистрации для пользователя.
    """
    now, expires_at = _calculate_expiration_time()

    try:
        new_code = _generate_registration_code()
    except ValueError as e:
        logger.error(f"Некорректные настройки генерации кода: {e}")
        raise

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        reg_code = _create_code_object(new_code, role, created_by_admin_id, now, expires_at)

        if await _try_save_code(db, reg_code, attempt):
            return reg_code

        if attempt < MAX_GENERATION_ATTEMPTS:
            try:
                new_code = _generate_registration_code()
            except ValueError as e:
                logger.error(f"Некорректные настройки генерации кода: {e}")
                raise

    logger.error(
        f"Не удалось сгенерировать уникальный код регистрации после "
        f"{MAX_GENERATION_ATTEMPTS} попыток."
    )
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


async def get_unused_registration_codes_count(db: AsyncSession) -> dict[Any, int]:
    """
    Получить количество неиспользованных кодов по ролям.
    """
    result = await db.execute(
        select(RegistrationCode.role, func.count())
        .where(RegistrationCode.is_used.is_(False))
        .group_by(RegistrationCode.role)
    )

    counts: dict[UserRole, int] = {UserRole(role): count for role, count in result.all()}
    return {
        UserRole.SHOP: counts.get(UserRole.SHOP, 0),
        UserRole.COURIER: counts.get(UserRole.COURIER, 0),
        UserRole.ADMIN: counts.get(UserRole.ADMIN, 0),
        "total": sum(counts.values()),
    }


# async def get_system_stats(db: AsyncSession) -> dict:
#     """
#     Получить системную статистику для администраторов.
#     Включает счетчики пользователей, заказов и споров.
#     """
#     # Статистика пользователей по ролям
#     user_counts = await db.execute(select(User.role, func.count(User.id)).group_by(User.role))
#     users = {role.value: count for role, count in user_counts.all()}
#     total_users = sum(users.values())

#     # Статистика заказов по статусам
#     order_counts = await db.execute(
#         select(Order.status, func.count(Order.id)).group_by(Order.status)
#     )
#     orders = {status.value: count for status, count in order_counts.all()}
#     total_orders = sum(orders.values())
#     completed_orders = orders.get(OrderStatus.COMPLETED.value, 0)
#     cancelled_orders = orders.get(OrderStatus.CANCELLED.value, 0)
#     active_orders = total_orders - completed_orders - cancelled_orders

#     # Статистика споров
#     dispute_counts = await db.execute(
#         select(Dispute.status, func.count(Dispute.id)).group_by(Dispute.status)
#     )
#     disputes = {status.value: count for status, count in dispute_counts.all()}
#     total_disputes = sum(disputes.values())
#     unresolved_disputes = (
#         total_disputes
#         # - disputes.get(DisputeStatus.CLOSED.value, 0)
#         - disputes.get(DisputeStatus.RESOLVED.value, 0)
#     )

#     return {
#         "total_users": total_users,
#         "total_admins": users.get(UserRole.ADMIN.value, 0),
#         "total_shops": users.get(UserRole.SHOP.value, 0),
#         "total_couriers": users.get(UserRole.COURIER.value, 0),
#         "total_orders": total_orders,
#         "active_orders": active_orders,
#         "completed_orders": completed_orders,
#         "cancelled_orders": cancelled_orders,
#         "total_disputes": total_disputes,
#         "unresolved_disputes": unresolved_disputes,
#     }


ModelType = TypeVar("ModelType")


async def get_all_couriers(
    db: AsyncSession,
    page: int,
    limit: int,
    status: UserStatus | None,
    search: str | None,
) -> PaginatedResponse[CourierCardResponse]:
    """
    Получает пагинированный список курьеров с возможностью фильтрации и поиска.
    """
    total, couriers = await get_paginated_list(
        db=db,
        model=Courier,
        page=page,
        limit=limit,
        status=status,
        status_field="status",
        status_model=User,
        search=search,
        search_fields=[Courier.full_name, User.username],
        joins=[(User, Courier.user_id == User.id)],
        eager_load_options=[contains_eager(Courier.user)],
        sort_by_field="id",
        sort_desc=False,
    )

    response_items = [CourierCardResponse.model_validate(courier) for courier in couriers]
    return PaginatedResponse(total=total, items=response_items)


async def get_all_shops(
    db: AsyncSession,
    page: int,
    limit: int,
    status: UserStatus | None,
    search: str | None,
) -> PaginatedResponse[ShopCardResponse]:
    """
    Получает пагинированный список магазинов с возможностью фильтрации и поиска.
    """
    total, shops = await get_paginated_list(
        db=db,
        model=Shop,
        page=page,
        limit=limit,
        status=status,
        status_field="status",
        status_model=User,
        search=search,
        search_fields=[Shop.name, User.username],
        joins=[(User, Shop.user_id == User.id)],
        eager_load_options=[contains_eager(Shop.user)],
        sort_by_field="id",
        sort_desc=False,
    )

    response_items = [ShopCardResponse.model_validate(shop) for shop in shops]
    return PaginatedResponse(total=total, items=response_items)


async def get_all_orders(
    db: AsyncSession,
    page: int,
    limit: int,
    status: OrderStatus | None,
    search: str | None,
) -> PaginatedResponse[OrderCardResponse]:
    """
    Получает пагинированный список заказов с возможностью фильтрации и поиска.
    """
    search_fields = [
        Order.shop.name,
        Order.courier.full_name,
        Order.description,
    ]

    total, orders = await get_paginated_list(
        db=db,
        model=Order,
        page=page,
        limit=limit,
        status=status,
        status_field="status",
        search=search,
        search_fields=search_fields,
        eager_load_options=[
            selectinload(Order.shop).options(load_only(Shop.name)),
            selectinload(Order.courier).options(load_only(Courier.full_name)),
        ],
        sort_by_field="created_at",
        sort_desc=True,
    )

    response_items = [OrderCardResponse.model_validate(order) for order in orders]
    return PaginatedResponse(total=total, items=response_items)


async def get_all_disputes(
    db: AsyncSession,
    page: int,
    limit: int,
    status: DisputeStatus | None,
    search: str | None,
) -> PaginatedResponse[DisputeCardResponse]:
    """
    Получить все споры с пагинацией и фильтрацией.
    Доступно только администраторам.
    """
    search_fields = [
        Dispute.description,
        Dispute.order.shop.name,
        Dispute.order.courier.full_name,
        Dispute.opened_by_user.username,
    ]

    total, disputes = await get_paginated_list(
        db=db,
        model=Dispute,
        page=page,
        limit=limit,
        status=status,
        status_field="status",
        search=search,
        search_fields=search_fields,
        joins=[
            (Order, Dispute.order_id == Order.id),
            (Shop, Order.shop_id == Shop.id),
            (Courier, Order.courier_id == Courier.id),
        ],
        eager_load_options=[
            selectinload(Dispute.order).selectinload(Order.shop),
            selectinload(Dispute.order).selectinload(Order.courier),
            selectinload(Dispute.opened_by_user),
        ],
        sort_by_field="created_at",
        sort_desc=True,
    )

    response_items = [DisputeCardResponse.from_dispute(d) for d in disputes]

    return PaginatedResponse(total=total, items=response_items)
