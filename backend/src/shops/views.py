from re import I

from fastapi import APIRouter

from backend.src.auth.dependencies import RequireAdminOrCourier
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.shop import Shop
from backend.src.shops import service
from backend.src.shops.schemas import ShopCardResponse

logger = get_logger(__name__)


router = APIRouter()


@router.get("/{shop_id}", response_model=ShopCardResponse)
async def get_shop_card(
    shop_id: int,
    current_user: RequireAdminOrCourier,
    db: DbSession,
) -> ShopCardResponse:
    """
    Получение карточки магазина.

    Args:
        shop_id: ID магазина
        current_user: Текущий аутентифицированный пользователь
        db: Сессия базы данных

    Returns:
        ShopCardResponse: Данные карточки магазина
    """
    logger.debug(f"Пользователь {current_user} запрашивает карточку магазина {shop_id=}")

    shop: Shop = await service.get_shop_card(shop_id, db)

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

    logger.info(f"Карточка магазина {shop} успешно сформирована для пользователя {current_user}")

    return response
