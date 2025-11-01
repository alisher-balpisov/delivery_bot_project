from fastapi import APIRouter

from backend.src.auth.dependencies import RequireAdminOrShop, RequireCourier
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.schemas.courier import CourierCardResponse, CourierRead

from . import service

logger = get_logger(__name__)

router = APIRouter()


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

    response = service.get_courier_card(db=db, courier_id=courier_id)

    logger.info(f"Карточка курьера {courier_id} успешно возвращена для пользователя {current_user}")
    return response


@router.patch("/toggle-shift", response_model=CourierRead)
async def toggle_shift(db: DbSession, current_user: RequireCourier):
    """
    Переключает активный статус курьера (выход на смену / уход со смены).
    """
    response = await service.toggle_shift(db=db, current_user=current_user)
    return response
