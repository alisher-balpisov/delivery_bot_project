from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from backend.src.common.enums import UserStatus
from backend.src.common.utils.paginaters import get_paginated_list
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.courier_rating import CourierRating
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
