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
    code: str,
    role: UserRole,
    created_by_admin_id: int,
    now: datetime,
    expires_at: datetime,
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


async def get_registration_codes(
    db: AsyncSession,
    page: int,
    limit: int,
    role: UserRole | None = None,
    is_used: bool | None = None,
) -> PaginatedResponse[RegistrationCodeResponse]:
    """
    Получить список кодов регистрации с пагинацией и фильтрацией.
    """
    query = select(RegistrationCode)

    if role:
        query = query.where(RegistrationCode.role == role)

    if is_used is not None:
        query = query.where(RegistrationCode.is_used == is_used)

    total_count = await db.scalar(select(func.count()).select_from(query.subquery()))

    query = (
        query.order_by(RegistrationCode.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )
    result = await db.execute(query)
    codes = result.scalars().all()

    response_items = [RegistrationCodeResponse.model_validate(code) for code in codes]
    return PaginatedResponse(total=total_count or 0, items=response_items)


async def get_registration_code_by_id(db: AsyncSession, code_id: int) -> RegistrationCode | None:
    """
    Получить код регистрации по ID.
    """
    return await db.get(RegistrationCode, code_id)


async def deactivate_registration_code(db: AsyncSession, code_id: int) -> RegistrationCode:
    """
    Деактивирует код регистрации (помечает как использованный или просроченный).
    В текущей реализации мы просто помечаем его как использованный, но без привязки к пользователю,
    либо можно установить expires_at в прошлое.
    По требованию: "Деактивировать просрочен = true (менять expires at или is_used хз первый вариант больше нравится)"
    Давайте менять expires_at на текущее время, чтобы он стал просроченным.
    """
    code = await get_registration_code_by_id(db, code_id)
    if not code:
        raise ValueError(f"Код с ID {code_id} не найден.")

    if code.is_used:
        raise ValueError("Код уже использован.")

    # Делаем код просроченным
    code.expires_at = datetime.now(UTC)
    db.add(code)
    await db.commit()
    await db.refresh(code)
    return code


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
    cancelled_orders = orders.get(OrderStatus.CANCELED.value, 0)
    active_orders = total_orders - completed_orders - cancelled_orders

    # Статистика споров
    dispute_counts = await db.execute(
        select(Dispute.status, func.count(Dispute.id)).group_by(Dispute.status)
    )
    disputes = {status.value: count for status, count in dispute_counts.all()}
    total_disputes = sum(disputes.values())
    unresolved_disputes = total_disputes - disputes.get(DisputeStatus.RESOLVED.value, 0)

    # Подсчет заказов за сегодня
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    orders_today_count = await db.scalar(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    )

    # Подсчет активных курьеров (со статусом ACTIVE)
    active_couriers_count = await db.scalar(
        select(func.count(User.id)).where(
            User.role == UserRole.COURIER, User.status == UserStatus.ACTIVE
        )
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
        "orders_today": orders_today_count or 0,
        "active_couriers": active_couriers_count or 0,
    }


async def get_order_by_id(db: AsyncSession, order_id: int) -> Order | None:
    """
    Получить заказ по ID с полной загрузкой связанных сущностей.
    """
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.shop),
            selectinload(Order.courier),
            selectinload(Order.history),
            selectinload(Order.dispute),
            selectinload(Order.rating),
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


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
        Shop.name,
        Courier.full_name,
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
        joins=[
            (Shop, Order.shop_id == Shop.id, True),  # type: ignore
            (Courier, Order.courier_id == Courier.id, True),  # type: ignore
        ],
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
        Shop.name,
        Courier.full_name,
        User.username,
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
            (Shop, Order.shop_id == Shop.id, True),  # type: ignore
            (Courier, Order.courier_id == Courier.id, True),  # type: ignore
            (User, Dispute.opened_by_user_id == User.id),
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
