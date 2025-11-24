from fastapi import APIRouter

from backend.src.auth.dependencies import RequireAdminOrCourier
from backend.src.common.dependencies import PaginationParams
from backend.src.common.enums import UserStatus
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.shop import Shop

from . import service
from .schemas import ShopCardResponse, ShopListItem, ShopListResponse

logger = get_logger(__name__)


router = APIRouter()


@router.get("/", response_model=ShopListResponse)
async def get_shops(
    current_user: RequireAdminOrCourier,
    db: DbSession,
    pagination: PaginationParams,
    status: UserStatus | None = None,
) -> ShopListResponse:
    """
    Получение списка магазинов.
    """
    page, limit = pagination
    shops, total = await service.get_shops_list(db, page, limit, status)

    items = [
        ShopListItem(
            id=shop.id,
            name=shop.name,
            status=shop.user.status,
            telegram_id=shop.user.telegram_id,
        )
        for shop in shops
    ]

    pages = (total + limit - 1) // limit

    return ShopListResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
    )


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
