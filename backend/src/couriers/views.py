from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from backend.src.auth.dependencies import RequireAllRoles
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.courier_rating import CourierRating
from backend.src.schemas.courier import CourierCardResponse

logger = get_logger(__name__)

router = APIRouter()


async def get_avg_rating(db, courier_id: int) -> float | None:
    result = await db.scalar(
        select(func.avg(CourierRating.rating)).where(
            CourierRating.courier_id == courier_id,
            CourierRating.rating.is_not(None),
        )
    )
    return result


@router.get("/couriers/{courier_id}", response_model=CourierCardResponse)
async def get_courier_card(
    courier_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Получение карточки курьера с кнопками на основе роли пользователя.

    Args:
        courier_id: ID курьера
        current_user: Текущий аутентифицированный пользователь
        db: Сессия базы данных

    Returns:
        CourierCardResponse: Данные карточки курьера с кнопками
    """
    logger.debug(f"Пользователь {current_user} запрашивает карточку курьера {courier_id}")

    # Получение данных курьера из базы данных
    courier = await db.get(Courier, courier_id)
    if courier is None:
        logger.warning(f"Курьер с ID {courier_id} не найден")
        raise HTTPException(status_code=404, detail="Курьер не найден")

    avg_rating = get_avg_rating(db, courier_id)

    # Формирование ответа
    response = CourierCardResponse(
        id=courier.id,
        telegram_id=courier.user.telegram_id,
        username=courier.user.username,
        full_name=courier.full_name,
        status=courier.user.status,
        phone_numbers=courier.phone_number,
        photo_id=courier.photo_id,
        is_active=courier.is_active,
        rating=avg_rating,
    )

    logger.info(f"Карточка курьера {courier_id} успешно возвращена для пользователя {current_user}")
    return response
