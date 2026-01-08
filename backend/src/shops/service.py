from collections.abc import Sequence
from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from backend.src.common.enums import DisputeStatus, OrderStatus, UserStatus
from backend.src.common.utils.paginaters import get_paginated_list
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
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


async def get_shop_stats(
    db: DbSession,
    shop_id: int,
) -> dict[str, int]:
    """
    Получение статистики магазина.

    Args:
        db: Сессия базы данных
        shop_id: ID магазина

    Returns:
        dict: Словарь со статистикой
    """
    # 1. Активные заказы (не завершенные и не отмененные)
    active_orders_query = select(func.count(Order.id)).where(
        Order.shop_id == shop_id,
        Order.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELED]),
    )
    active_orders = await db.scalar(active_orders_query) or 0

    # 2. Заказы за сегодня
    today_start = func.current_date()
    orders_today_query = select(func.count(Order.id)).where(
        Order.shop_id == shop_id,
        func.date(Order.created_at) == today_start,
    )
    orders_today = await db.scalar(orders_today_query) or 0

    # 3. Активные споры (не закрытые)
    # Споры привязаны к заказу, заказ привязан к магазину
    active_disputes_query = (
        select(func.count(Dispute.id))
        .join(Order, Dispute.order_id == Order.id)
        .where(
            Order.shop_id == shop_id,
            Dispute.status != DisputeStatus.RESOLVED,
        )
    )
    active_disputes = await db.scalar(active_disputes_query) or 0

    return {
        "active_orders": active_orders,
        "orders_today": orders_today,
        "active_disputes": active_disputes,
    }


async def update_shop_profile(
    db: DbSession,
    shop_id: int,
    data: dict,
) -> Shop:
    """
    Обновление профиля магазина.
    """
    shop = await get_shop_card(shop_id, db)

    for key, value in data.items():
        if value is not None:
            setattr(shop, key, value)

    await db.commit()
    await db.refresh(shop)
    return shop
