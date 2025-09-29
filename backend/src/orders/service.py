from datetime import datetime

from backend.src.common.enums import OrderStatus, OrderType, UserRole
from backend.src.core.logging import get_logger
from backend.src.models.order import Order
from backend.src.models.user import User
from backend.src.models.zone import Zone
from backend.src.schemas.order import OrderCreate, OrderResponse, OrderUpdate
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def create_order(db: AsyncSession, order_data: OrderCreate) -> OrderResponse:
    # ... (this function remains the same)
    logger.debug(
        f"Создание заказа с данными: {order_data.shop_id}, зона {order_data.zone_id}, тип {order_data.order_type}"
    )
    zone = await db.get(Zone, order_data.zone_id)
    if not zone:
        raise ValueError("Указанная зона не найдена")

    base_price = zone.base_price
    if order_data.order_type == OrderType.special:
        pass
    elif order_data.order_type == OrderType.rush_hour:
        if order_data.rush_hour_addon == 0:
            order_data.rush_hour_addon = 1000.0
    elif order_data.order_type == OrderType.long_distance:
        if order_data.zone_addon == 0:
            order_data.zone_addon = 500.0
    elif order_data.order_type == OrderType.important:
        base_price = 0

    total_price = base_price + order_data.zone_addon + order_data.rush_hour_addon

    order = Order(**order_data.model_dump(), price=total_price)

    async with db.begin():
        db.add(order)
        # flush нужен, чтобы получить order.id и другие поля, генерируемые БД,
        # до фактического коммита транзакции.
        await db.flush()
        await db.refresh(order)

    return OrderResponse.model_validate(order)


async def get_order_by_id(db: AsyncSession, order_id: int) -> OrderResponse | None:
    # ... (this function remains the same)
    order = await db.get(Order, order_id)
    return OrderResponse.model_validate(order) if order else None


async def update_order(
    db: AsyncSession, order_id: int, update_data: OrderUpdate, current_user: User
) -> OrderResponse:
    """
    Обновление статуса заказа с проверкой прав доступа.
    """
    async with db.begin():
        order = await db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

        # --- Authorization Logic ---
        user_role = current_user.role
        update_dict = update_data.model_dump(exclude_unset=True)

        if user_role == UserRole.ADMIN:
            logger.info(f"Admin {current_user.id} is updating order {order_id}")
        elif user_role == UserRole.SHOP:
            if not current_user.shop or order.shop_id != current_user.shop.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому заказу"
                )
            if "status" in update_dict and update_dict["status"] != OrderStatus.CANCELLED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Магазин может только отменить заказ",
                )
            if order.status != OrderStatus.CREATED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Можно отменить только новый заказ",
                )
        elif user_role == UserRole.COURIER:
            if not current_user.courier or order.courier_id != current_user.courier.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Заказ не назначен вам"
                )
            allowed_fields = {"status", "courier_notes", "completion_notes"}
            if not set(update_dict.keys()).issubset(allowed_fields):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Вы можете изменять только статус и заметки",
                )
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

        # --- Update Logic ---
        old_status = order.status
        for key, value in update_dict.items():
            setattr(order, key, value)

        now = datetime.now()
        new_status = order.status

        if new_status != old_status:
            if new_status == OrderStatus.DELIVERED:
                order.delivered_at = now
            elif new_status == OrderStatus.COMPLETED:
                order.confirmed_at = now
            logger.info(
                f"Статус заказа {order_id} изменён с {old_status.value} на {new_status.value} пользователем {current_user.id}"
            )


    # после выхода из блока — данные зафиксированы
    await db.refresh(order)
    return OrderResponse.model_validate(order)
