from fastapi import APIRouter, HTTPException

from backend.src.auth.dependencies import RequireAdminOrShop, RequireCourier
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.schemas.courier import CourierCardResponse, CourierShiftResponse

from . import service

logger = get_logger(__name__)

router = APIRouter()


@router.get("/shift")
async def get_courier_shift_status(
    current_user: RequireCourier,
) -> bool:
    """
    Получить статус смены текущего курьера.
    """
    logger.debug(f"Курьер {current_user} запрашивает статус смены.")
    return current_user.courier.is_active  # type: ignore


@router.patch("/toggle-shift", response_model=CourierShiftResponse)
async def toggle_shift(
    db: DbSession,
    current_user: RequireCourier,
):
    """
    Начать или завершить смену (переключить статус is_active).
    """
    logger.debug(f"Курьер {current_user} пытается изменить статус смены.")

    courier = await service.toggle_courier_shift(db=db, current_user=current_user)

    logger.info(f"Курьер {current_user} изменил статус смены на {courier.is_active}")
    return courier


@router.get("/{courier_id}", response_model=CourierCardResponse)
async def get_courier_card(
    courier_id: int,
    current_user: RequireAdminOrShop,
    db: DbSession,
):
    """
    Получение карточки курьера с кнопками на основе роли пользователя.
    """
    logger.debug(f"Пользователь {current_user} запрашивает карточку курьера {courier_id}")

    try:
        response = await service.get_courier_card(db=db, courier_id=courier_id)
    except ValueError:
        logger.warning(
            f"Попытка доступа к несуществующему курьеру {courier_id} от пользователя {current_user}"
        )
        raise HTTPException(status_code=404, detail="Курьер не найден")

    logger.info(f"Карточка курьера {courier_id} успешно возвращена для пользователя {current_user}")
    return response
