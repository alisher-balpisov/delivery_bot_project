from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.common.enums import OrderStatus, OrderType, UserRole
from backend.src.core.logging import get_logger
from backend.src.models.order import Order
from backend.src.models.user import User
from backend.src.schemas.order import OrderCreate, OrderResponse, OrderUpdate

logger = get_logger(__name__)


async def create_order(db: AsyncSession, order_data: OrderCreate) -> OrderResponse:
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
        f"Создание заказа для магазина {order_data.shop_id}, тип: {order_data.order_type}"
    )

    # Для special заказов проверяем, что указан курьер
    if order_data.order_type == OrderType.SPECIAL and not order_data.courier_id:
        logger.warning("Попытка создать специальный заказ без указания курьера")
        # Для специального заказа courier_id может быть опциональным
        # в зависимости от бизнес-логики
        pass

    # Создаем заказ с начальным статусом PENDING
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

    logger.info(f"Заказ создан успешно: id={order.id}, магазин={order.shop_id}")
    return OrderResponse.model_validate(order)


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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
            )

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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав"
            )

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
