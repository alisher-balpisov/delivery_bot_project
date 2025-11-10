from http import HTTPStatus

from fastapi import HTTPException

from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.shop import Shop

logger = get_logger(__name__)


async def get_shop_card(
    shop_id: int,
    db: DbSession,
) -> Shop:
    """
    Получение данных для карточки магазина.

    Args:
        shop_id: ID магазина
        current_user: Текущий аутентифицированный пользователь
        db: Сессия базы данных

    Returns:
        ShopCardResponse: Данные карточки магазина
    """

    shop = await db.get(Shop, shop_id)
    if not shop:
        logger.warning(f"Магазин с {shop_id=} не найден")
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Магазин не найден")

    return shop
