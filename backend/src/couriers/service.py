from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.courier_rating import CourierRating
from backend.src.models.user import User
from backend.src.schemas.courier import CourierCardResponse

logger = get_logger(__name__)

async def get_shift_status(current_user: User) -> Courier:
    """
    Получает статус смены текущего аутентифицированного курьера.
    """
    return current_user.courier

async def toggle_courier_shift(
    db: AsyncSession,
    current_user: User,
) -> Courier:
    """
    Переключает статус смены (is_active) для текущего курьера.
    """
    courier = current_user.courier
    if not courier:
        return None

    courier.is_active = not courier.is_active

    db.add(courier)
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


async def get_courier_card(db: DbSession, courier_id: int) -> CourierCardResponse:
    """
    Сервисная функция: собирает и возвращает CourierCardResponse для указанного courier_id.
    Бросает ValueError, если курьер не найден, или SQLAlchemyError при проблемах с БД.
    """
    try:
        courier = await db.get(Courier, courier_id)
    except SQLAlchemyError as e:
        logger.exception(f"Ошибка базы данных при выборке courier_id={courier_id}: {e}")
        raise

    if courier is None:
        logger.warning("Курьер с ID %s не найден в БД", courier_id)
        raise ValueError("Courier not found")

    avg_rating = await get_avg_rating(db, courier_id)

    phone_numbers = list(courier.phone_number)

    card = CourierCardResponse(
        id=int(courier.id),
        telegram_id=int(courier.user.telegram_id)
        if courier.user and courier.user.telegram_id
        else None,
        username=courier.user.username if courier.user and courier.user.username else None,
        full_name=courier.full_name,
        status=courier.user.status if courier.user else None,
        phone_numbers=phone_numbers,
        photo_id=courier.photo_id,
        is_active=bool(courier.is_active),
        rating=avg_rating,
    )

    return card

