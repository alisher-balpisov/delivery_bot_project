import secrets
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from backend.src.common.enums import DisputeStatus, OrderStatus, UserRole, UserStatus
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.shop import Shop
from backend.src.models.user import User
from backend.src.schemas.admin import RegistrationCodeResponse
from backend.src.schemas.courier import CourierCardResponse
from backend.src.schemas.dispute import DisputeCardResponse
from backend.src.schemas.order import OrderCardResponse
from backend.src.schemas.shop import ShopCardResponse

logger = get_logger(__name__)

T = TypeVar("T")


class PaginatedResponse[T](BaseModel):
    total: int = Field(..., description="Общее количество элементов")
    items: list[T] = Field(..., description="Список элементов на текущей странице")


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


ModelType = TypeVar("ModelType")


async def _get_paginated_list[ModelType](
    db: AsyncSession,
    model: type[ModelType],
    page: int,
    limit: int,
    join_model: type,
    join_on: Column,
    search_fields: list[Column],
    status: UserStatus | None = None,
    search: str | None = None,
) -> tuple[int, list[ModelType]]:
    """
    Обобщенная функция для получения пагинированного списка сущностей.
    """
    # 1. Формируем список фильтров
    filters = []
    if status:
        filters.append(join_model.status == status)

    if search:
        search_term = f"%{search.lower()}%"
        search_conditions = [func.lower(field).like(search_term) for field in search_fields]
        filters.append(or_(*search_conditions))

    # 2. Запрос для подсчета общего количества записей с фильтрами
    total_query = select(func.count(model.id)).join(join_model, join_on)
    if filters:
        total_query = total_query.where(*filters)

    total = await db.scalar(total_query)
    if not total:
        return 0, []

    # 3. Запрос для получения данных с фильтрами и пагинацией
    data_query = select(model).join(join_model, join_on).options(contains_eager(model.user))
    if filters:
        data_query = data_query.where(*filters)

    data_query = data_query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(data_query)
    items = result.scalars().all()

    return total, items


async def get_all_couriers(
    db: AsyncSession,
    page: int,
    limit: int,
    status: UserStatus | None,
    search: str | None,
) -> PaginatedResponse[CourierCardResponse]:
    total, couriers = await _get_paginated_list(
        db=db,
        model=Courier,
        page=page,
        limit=limit,
        join_model=User,
        join_on=(Courier.user_id == User.id),
        search_fields=[Courier.full_name, User.username],
        status=status,
        search=search,
    )

    response_items = [
        CourierCardResponse(
            id=courier.id,
            telegram_id=courier.user.telegram_id,
            username=courier.user.username,
            full_name=courier.full_name,
            status=courier.user.status,
            phone_numbers=courier.phone_number,
            photo_id=courier.photo_id,
            is_active=courier.is_active,
            rating=None,
        )
        for courier in couriers
    ]

    return PaginatedResponse(total=total, items=response_items)


async def get_all_shops(
    db: AsyncSession,
    page: int,
    limit: int,
    status: UserStatus | None,
    search: str | None,
) -> PaginatedResponse[ShopCardResponse]:
    total, shops = await _get_paginated_list(
        db=db,
        model=Shop,
        page=page,
        limit=limit,
        join_model=User,
        join_on=(Shop.user_id == User.id),
        search_fields=[Shop.name, User.username],
        status=status,
        search=search,
    )

    response_items = [
        ShopCardResponse(
            id=shop.id,
            telegram_id=shop.user.telegram_id,
            username=shop.user.username,
            name=shop.name,
            status=shop.user.status,
            address=shop.address,
            address_link=shop.address_link,
            phone_numbers=shop.phone_number,
        )
        for shop in shops
    ]

    return PaginatedResponse(total=total, items=response_items)


async def get_all_orders(
    db: AsyncSession,
    page: int,
    limit: int,
    status: OrderStatus | None,
    search: str | None,
) -> PaginatedResponse[OrderCardResponse]:
    """
    Получить все заказы с пагинацией и фильтрацией.
    Доступно только администраторам.
    """
    # Формируем фильтры
    filters = []
    if status:
        filters.append(Order.status == status)

    if search:
        search_term = f"%{search.lower()}%"
        # Поиск по адресу получателя, описанию или телефону клиента
        filters.append(
            or_(
                func.lower(Order.recipient_address).like(search_term),
                func.lower(Order.description).like(search_term),
                func.lower(Order.client_phone).like(search_term),
            )
        )

    # Подсчет общего количества
    total_query = select(func.count(Order.id))
    if filters:
        total_query = total_query.where(*filters)

    total = await db.scalar(total_query)
    if not total:
        return PaginatedResponse(total=0, items=[])

    # Получение данных с пагинацией
    data_query = (
        select(Order)
        .options(selectinload(Order.shop), selectinload(Order.courier))
        .order_by(Order.created_at.desc())
    )
    if filters:
        data_query = data_query.where(*filters)

    data_query = data_query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(data_query)
    orders = result.scalars().all()

    response_items = [
        OrderCardResponse(
            id=order.id,
            shop_id=order.shop_id,
            shop_name=order.shop.name if order.shop else None,
            courier_id=order.courier_id,
            courier_name=order.courier.full_name if order.courier else None,
            status=order.status,
            order_type=order.order_type,
            special_type=order.special_type,
            price=order.price,
            recipient_address=order.recipient_address,
            created_at=order.created_at,
        )
        for order in orders
    ]

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
    # Формируем фильтры
    filters = []
    if status:
        filters.append(Dispute.status == status)

    if search:
        search_term = f"%{search.lower()}%"
        # Поиск по описанию спора
        filters.append(func.lower(Dispute.description).like(search_term))

    # Подсчет общего количества
    total_query = select(func.count(Dispute.id))
    if filters:
        total_query = total_query.where(*filters)

    total = await db.scalar(total_query)
    if not total:
        return PaginatedResponse(total=0, items=[])

    # Получение данных с пагинацией
    data_query = (
        select(Dispute)
        .options(
            selectinload(Dispute.order).selectinload(Order.shop),
            selectinload(Dispute.order).selectinload(Order.courier),
            selectinload(Dispute.opened_by_user),
        )
        .order_by(Dispute.created_at.desc())
    )
    if filters:
        data_query = data_query.where(*filters)

    data_query = data_query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(data_query)
    disputes = result.scalars().all()

    response_items = [
        DisputeCardResponse(
            id=dispute.id,
            order_id=dispute.order_id,
            shop_id=dispute.order.shop_id,
            shop_name=dispute.order.shop.name if dispute.order.shop else None,
            courier_id=dispute.order.courier_id,
            courier_name=dispute.order.courier.full_name if dispute.order.courier else None,
            status=dispute.status,
            created_by_role=dispute.opened_by_user.role if dispute.opened_by_user else None,
            description=dispute.description,
            created_at=dispute.created_at,
            resolved_at=dispute.resolved_at,
        )
        for dispute in disputes
    ]

    return PaginatedResponse(total=total, items=response_items)
