from collections.abc import Sequence
from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from backend.src.common.enums import UserStatus
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
    query = select(Shop).join(User).options(joinedload(Shop.user))

    if status:
        query = query.where(User.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    shops = result.scalars().all()

    return shops, total
