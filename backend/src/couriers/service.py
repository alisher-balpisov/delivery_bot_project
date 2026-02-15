from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from backend.src.common.enums import OrderStatus, UserStatus
from backend.src.common.utils.paginaters import get_paginated_list
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.courier_rating import CourierRating
from backend.src.models.order import Order
from backend.src.models.user import User

logger = get_logger(__name__)


async def toggle_courier_shift(
    db: AsyncSession,
    current_user: User,
) -> Courier:
    """
    Переключает статус смены (is_active) для текущего курьера.
    """
    courier = current_user.courier
    if not courier:
        raise HTTPException(status_code=404, detail="Профиль курьера не найден.")

    courier.is_active = not courier.is_active

    await db.commit()
    await db.refresh(courier)

    return courier


async def get_avg_rating(db: DbSession, courier_id: int) -> float | None:
    """
    Возвращает средний рейтинг курьера как float или None, если оценок нет.
    """
    try:
        result = await db.scalar(
            select(func.avg(CourierRating.rating)).where(
                CourierRating.courier_id == courier_id,
                CourierRating.rating.is_not(None),
            )
        )
        return float(result) if result is not None else None
    except SQLAlchemyError as e:
        logger.exception(f"Ошибка при получении среднего рейтинга для courier_id={courier_id}: {e}")
        raise


async def get_courier_card(
    db: DbSession, courier_id: int
) -> tuple[Courier, float | None, list[str]]:
    """
    Сервисная функция: собирает и возвращает CourierCardResponse для указанного courier_id.
    Бросает ValueError, если курьер не найден, или SQLAlchemyError при проблемах с БД.
    """
    courier = await db.get(Courier, courier_id)

    if courier is None:
        logger.warning(f"Курьер с id={courier_id} не найден в БД")
        raise ValueError("Courier not found")

    avg_rating = await get_avg_rating(db, courier_id)

    phone_numbers = courier.phone_number if courier.phone_number else []

    return courier, avg_rating, phone_numbers


async def get_couriers(
    db: DbSession,
    page: int,
    size: int,
    status_filter: str | None = None,
) -> tuple[list[Courier], int]:
    """
    Получает список курьеров с пагинацией и фильтрацией.
    status_filter: 'active', 'inactive', 'on_shift', 'all'
    """
    status_model = User
    status_field = "status"
    status_value = None

    if status_filter == "active":
        status_value = UserStatus.ACTIVE
    elif status_filter == "inactive":
        status_value = UserStatus.INACTIVE
    elif status_filter == "on_shift":
        status_model = Courier
        status_field = "is_active"
        status_value = True

    # Для 'all' или неизвестного фильтра status_value останется None, фильтрация не применится

    total, couriers = await get_paginated_list(
        db=db,
        model=Courier,
        page=page,
        limit=size,
        status=status_value,
        status_field=status_field,
        status_model=status_model,
        joins=[(User, Courier.user_id == User.id)],
        eager_load_options=[contains_eager(Courier.user)],
        sort_by_field="id",
        sort_desc=False,
    )

    return couriers, total


async def get_active_couriers_for_selection(
    db: AsyncSession, page: int = 1, limit: int = 5
) -> tuple[list[dict], int]:
    """
    Возвращает список активных курьеров с количеством заказов и рейтингом.
    Используется магазином для выбора курьера вручную.
    """
    offset = (page - 1) * limit

    # Подзапрос для подсчета активных заказов
    active_orders_subq = (
        select(Order.courier_id, func.count(Order.id).label("active_orders_count"))
        .where(Order.status.in_(OrderStatus.active_statuses_for_courier()))
        .group_by(Order.courier_id)
        .subquery()
    )

    # Подзапрос для среднего рейтинга
    rating_subq = (
        select(CourierRating.courier_id, func.avg(CourierRating.rating).label("avg_rating"))
        .group_by(CourierRating.courier_id)
        .subquery()
    )

    # Базовый запрос
    base_query = (
        select(
            Courier,
            func.coalesce(active_orders_subq.c.active_orders_count, 0).label("active_orders"),
            func.coalesce(rating_subq.c.avg_rating, 0.0).label("rating"),
        )
        .join(User, Courier.user_id == User.id)
        .outerjoin(active_orders_subq, Courier.id == active_orders_subq.c.courier_id)
        .outerjoin(rating_subq, Courier.id == rating_subq.c.courier_id)
        .where(
            Courier.is_active.is_(True),
            User.status == UserStatus.ACTIVE,
        )
    )

    # Получаем общее количество
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_stmt) or 0

    # Добавляем сортировку и пагинацию
    stmt = base_query.order_by("active_orders", "rating").limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    couriers_data = []
    for row in rows:
        courier, active_orders, rating = row
        couriers_data.append(
            {
                "id": courier.id,
                "full_name": courier.full_name,
                "active_orders_count": active_orders,
                "rating": float(rating) if rating else 0.0,
            }
        )

    return couriers_data, total
