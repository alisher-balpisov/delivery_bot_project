from fastapi import APIRouter, HTTPException

from backend.src.auth.dependencies import RequireAllRoles
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.shop import Shop
from backend.src.schemas.shop import ShopCardResponse

logger = get_logger(__name__)

router = APIRouter()


@router.get("/{shop_id}", response_model=ShopCardResponse)
async def get_shop_card(
    shop_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Получение карточки магазина с кнопками на основе роли пользователя.

    Args:
        shop_id: ID магазина
        current_user: Текущий аутентифицированный пользователь
        db: Сессия базы данных

    Returns:
        ShopCardResponse: Данные карточки магазина с кнопками
    """
    logger.debug(f"Пользователь {current_user} запрашивает карточку магазина {shop_id}")

    # Получение данных магазина из базы данных
    shop = await db.get(Shop, shop_id)
    if shop is None:
        logger.warning(f"Магазин с ID {shop_id} не найден")
        raise HTTPException(status_code=404, detail="Магазин не найден")

    # Формирование ответа
    response = ShopCardResponse(
        id=shop.id,
        telegram_id=shop.user.telegram_id,
        username=shop.user.username,
        name=shop.name,
        status=shop.user.status,
        address=shop.address,
        address_link=shop.address_link,
        phone_numbers=shop.phone_number,
    )

    logger.info(f"Карточка магазина {shop} успешно возвращена для пользователя {current_user}")
    return response
