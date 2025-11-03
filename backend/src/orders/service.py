import select
from datetime import UTC, datetime
from tkinter import NO

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.src.common.enums import OrderStatus, OrderType, UserRole
from backend.src.core.logging import get_logger
from backend.src.models import Order
from backend.src.models.courier import Courier
from backend.src.models.order import Order
from backend.src.models.shop import Shop
from backend.src.models.user import User
from backend.src.orders.exceptions import NO_ACCESS_EXCEPTION
from backend.src.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderResponseForAdmin,
    OrderResponseForCourier,
    OrderResponseForShop,
    OrderUpdate,
)

logger = get_logger(__name__)


async def create_order(db: AsyncSession, order_data: OrderCreate) -> Order:
    """
    Создание нового заказа.

    Args:
        db: Сессия базы данных
        order_data: Данные заказа

    Returns:
        OrderResponse: Созданный заказ

    Raises:
        ValueError: Если данные невалидны
    """
    logger.debug(
        f"Создание заказа для магазина shop_id={order_data.shop_id}, order_type={order_data.order_type}"
    )

    order = Order(
        shop_id=order_data.shop_id,
        courier_id=order_data.courier_id,
        status=OrderStatus.PENDING,
        order_type=order_data.order_type,
        special_type=order_data.special_type,
        price=order_data.price,
        client_phone=order_data.client_phone,
        recipient_address=order_data.recipient_address,
        recipient_phone=order_data.recipient_phone,
        delivery_time=order_data.delivery_time,
        description=order_data.description,
    )

    async with db.begin():
        db.add(order)
        await db.flush()
        await db.refresh(order)

    logger.info(f"Заказ создан успешно: id={order.id}, магазин={order.shop}")
    return order


async def get_order_by_id(db: AsyncSession, order_id: int) -> OrderResponse | None:
    """
    Получение заказа по ID.

    Args:
        db: Сессия базы данных
        order_id: ID заказа

    Returns:
        OrderResponse или None если заказ не найден
    """
    order = await db.get(Order, order_id)
    return OrderResponse.model_validate(order) if order else None


async def update_order(
    db: AsyncSession, order_id: int, update_data: OrderUpdate, current_user: User
) -> OrderResponse:
    """
    Обновление заказа с проверкой прав доступа.

    Args:
        db: Сессия базы данных
        order_id: ID заказа
        update_data: Данные для обновления
        current_user: Текущий пользователь

    Returns:
        OrderResponse: Обновленный заказ

    Raises:
        HTTPException: Если заказ не найден или нет прав доступа
    """
    async with db.begin():
        order = await db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

        # Проверка прав доступа
        user_role = current_user.role
        update_dict = update_data.model_dump(exclude_unset=True)

        if user_role == UserRole.ADMIN:
            logger.info(f"Админ {current_user.id} обновляет заказ {order_id}")
        elif user_role == UserRole.SHOP:
            if not current_user.shop or order.shop_id != current_user.shop.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет доступа к этому заказу",
                )
            # Магазин может только отменить заказ
            if "status" in update_dict and update_dict["status"] != OrderStatus.CANCELED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Магазин может только отменить заказ",
                )
        elif user_role == UserRole.COURIER:
            if not current_user.courier or order.courier_id != current_user.courier.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Заказ не назначен вам",
                )
            # Курьер может изменять только статус и заметки
            allowed_fields = {"status", "courier_notes", "completion_notes"}
            if not set(update_dict.keys()).issubset(allowed_fields):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Вы можете изменять только статус и заметки",
                )
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

        # Обновление полей
        old_status = order.status
        for key, value in update_dict.items():
            setattr(order, key, value)

        # Обновление временных меток при изменении статуса
        now = datetime.now(UTC)
        new_status = order.status

        if new_status != old_status:
            if new_status == OrderStatus.COMPLETED:
                order.completed_at = now
            logger.info(
                f"Статус заказа {order_id} изменён с {old_status.value} на {new_status.value} "
                f"пользователем {current_user.id}"
            )

    await db.refresh(order)
    return OrderResponse.model_validate(order)


async def get_order(
    db: AsyncSession, user_id: int, order_id: int, user_role: UserRole
) -> OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier:
    """
    Возвращает информацию о заказе order_id, разную в зависимости от роли user_role пользователя user_id.

    Args:
        db: Сессия базы данных
        order_id: ID заказа
        user_id: ID пользователя
        user_role: Роль пользователя

    Returns:
        OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier: Информация о заказе в зависимости от роли пользователя

    Raises:
        HTTPException: Если заказ не найден или нет прав доступа
    """
    logger.info(
        f"Получение заказа order_id={order_id} для пользователя user_id={user_id} "
        f"с ролью user_role={user_role}"
    )

    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            joinedload(Order.shop).joinedload(Shop.user),
            joinedload(Order.courier).joinedload(Courier.user),
            joinedload(Order.history),
        )
    )

    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    if user_role == UserRole.ADMIN:
        logger.debug(f"Админ {user_id} получает заказ {order_id}")
        return OrderResponseForAdmin.model_validate(order)

    elif user_role == UserRole.SHOP:
        if order.shop.user_id != user_id:
            raise HTTPException(NO_ACCESS_EXCEPTION)
        return OrderResponseForShop.model_validate(order)

    elif user_role == UserRole.COURIER:
        if order.courier.user_id != user_id:
            raise HTTPException(NO_ACCESS_EXCEPTION)
        return OrderResponseForCourier.model_validate(order)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Недостаточно прав доступа",
    )
