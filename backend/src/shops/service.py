from collections.abc import Sequence
from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import joinedload

from backend.src.common.enums import UserStatus
from backend.src.common.utils.paginaters import get_paginated_list
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.shop import Shop
from backend.src.models.user import User

logger = get_logger(__name__)


async def get_shop_card(
    shop_id: int,
    db: DbSession,
) -> Shop:
    """
    Получение данных для карточки магазина.

    Args:
        shop_id: ID магазина
        db: Сессия базы данных

    Returns:
        Shop: Объект магазина
    """

    shop = await db.get(Shop, shop_id)
    if not shop:
        logger.warning(f"Магазин с {shop_id=} не найден")
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Магазин не найден")

    return shop


async def get_shops_list(
    db: DbSession,
    page: int = 1,
    limit: int = 10,
    status: UserStatus | None = None,
) -> tuple[Sequence[Shop], int]:
    """
    Получение списка магазинов с пагинацией и фильтрацией.
    """
    total, shops = await get_paginated_list(
        db=db,
        model=Shop,
        page=page,
        limit=limit,
        status=status,
        status_field="status",
        status_model=User,
        joins=[(User, Shop.user_id == User.id)],
        eager_load_options=[joinedload(Shop.user)],
        sort_by_field="id",
        sort_desc=False,
    )

    return shops, total
