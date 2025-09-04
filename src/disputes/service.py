from sqlalchemy.ext.asyncio import AsyncSession
from src.core.logging import get_logger
from src.models.dispute import Dispute
from src.models.order import Order
from src.schemas.dispute import DisputeCreate, DisputeRead, DisputeUpdate


async def create_dispute(db: AsyncSession, dispute_data: DisputeCreate) -> DisputeRead:
    """
    Создает новый спор по заказу.

    Args:
        db: Сессия базы данных.
        dispute_data: Данные для создания спора.

    Returns:
        Схема с данными созданного спора.
    """

    logger = get_logger(__name__)

    logger.info(
        f"Создание спора для заказа {dispute_data.order_id} с описанием: {dispute_data.description[:50]}..."
    )

    # TODO: Добавить проверку, что по этому заказу еще нет спора (уже в модели unique=True, но проверить ошибку)
    # TODO: Получить shop_id и courier_id из заказа
    order = await db.get(Order, dispute_data.order_id)
    if not order:
        logger.warning(f"Заказ {dispute_data.order_id} не найден.")
        raise ValueError("Order not found")

    if not order.courier_id:
        logger.warning(f"Заказ {dispute_data.order_id} без курьера.")
        raise ValueError("Cannot create a dispute for an order without a courier")

    logger.info(f"Данные заказа получены: shop_id={order.shop_id}, courier_id={order.courier_id}")

    new_dispute = Dispute(
        order_id=dispute_data.order_id,
        description=dispute_data.description,
        created_by_role=dispute_data.created_by_role,
        shop_id=order.shop_id,
        courier_id=order.courier_id,
    )

    logger.info(f"Добавление спора в БД: {new_dispute}")

    try:
        db.add(new_dispute)
        await db.commit()
        await db.refresh(new_dispute)
        logger.info(f"Спор успешно создан с ID {new_dispute.id}")
        return DisputeRead.from_orm(new_dispute)
    except Exception as e:
        logger.error(f"Ошибка при создании спора: {e}")
        raise


async def get_dispute_by_id(db: AsyncSession, dispute_id: int) -> DisputeRead | None:
    """
    Получает спор по его ID.

    Args:
        db: Сессия базы данных.
        dispute_id: ID спора.

    Returns:
        Схема с данными спора или None, если спор не найден.
    """

    logger = get_logger(__name__)

    logger.info(f"Получение спора ID {dispute_id}")

    dispute = await db.get(Dispute, dispute_id)
    if dispute:
        logger.info(f"Спор найден: order_id={dispute.order_id}, status={dispute.status}")
        return DisputeRead.from_orm(dispute)
    else:
        logger.warning(f"Спор ID {dispute_id} не найден.")
    return None


async def update_dispute(
    db: AsyncSession, dispute_id: int, update_data: DisputeUpdate
) -> DisputeRead | None:
    """
    Обновляет данные спора (для админов).

    Args:
        db: Сессия базы данных.
        dispute_id: ID спора для обновления.
        update_data: Данные для обновления.

    Returns:
        Схема с обновленными данными спора или None, если спор не найден.
    """

    logger = get_logger(__name__)

    logger.info(
        f"Обновление спора ID {dispute_id} с данными: {update_data.dict(exclude_unset=True)}"
    )

    dispute = await db.get(Dispute, dispute_id)
    if not dispute:
        logger.warning(f"Спор ID {dispute_id} не найден.")
        return None

    logger.info(f"Найден спор: status={dispute.status}, created_by={dispute.created_by_role}")

    update_data_dict = update_data.dict(exclude_unset=True)
    logger.info(f"Поля для обновления: {update_data_dict}")

    for key, value in update_data_dict.items():
        setattr(dispute, key, value)

    logger.info(f"Обновленные поля: {update_data_dict}")

    try:
        await db.commit()
        await db.refresh(dispute)
        logger.info(f"Спор ID {dispute_id} успешно обновлен.")
        return DisputeRead.from_orm(dispute)
    except Exception as e:
        logger.error(f"Ошибка при обновлении спора ID {dispute_id}: {e}")
        raise
