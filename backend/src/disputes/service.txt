from backend.src.core.logging import get_logger
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
from backend.src.models.user import User
from backend.src.schemas.dispute import DisputeCreate, DisputeRead, DisputeUpdate
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def create_dispute(
    db: AsyncSession, dispute_data: DisputeCreate, initiator: User
) -> DisputeRead:
    """
    Создает новый спор по заказу.

    Args:
        db: Сессия базы данных.
        dispute_data: Данные для создания спора.
        initiator: Пользователь, который создает спор (из токена).
    """
    logger.info(f"User {initiator.id} creating dispute for order {dispute_data.order_id}")

    order = await db.get(Order, dispute_data.order_id)
    if not order:
        logger.warning(f"Order {dispute_data.order_id} not found.")
        raise ValueError("Заказ не найден")

    # Authorization check within the service
    is_shop = initiator.shop and initiator.shop.id == order.shop_id
    is_courier = initiator.courier and initiator.courier.id == order.courier_id
    if not (is_shop or is_courier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы можете открывать споры только по своим заказам",
        )

    if not order.courier_id:
        raise ValueError("Невозможно создать спор для заказа без курьера")

    new_dispute = Dispute(
        order_id=dispute_data.order_id,
        description=dispute_data.description,
        created_by_role=initiator.role,  # Role is from the trusted initiator object
        shop_id=order.shop_id,
        courier_id=order.courier_id,
    )

    try:
        async with db.begin():
            db.add(new_dispute)
            # Используем flush, чтобы получить ID нового спора до завершения транзакции.
            # Это полезно для логирования или если ID нужен для последующих операций.
            await db.flush()
            await db.refresh(new_dispute)

        logger.info(f"Dispute created successfully with ID {new_dispute.id}")
        return DisputeRead.model_validate(new_dispute)
    except Exception as e:
        # Контекстный менеджер `async with db.begin()` уже выполнил rollback при ошибке.
        # Мы просто логируем исключение перед его передачей выше.
        logger.error(f"Error creating dispute: {e}")
        raise


async def get_dispute_by_id(db: AsyncSession, dispute_id: int) -> DisputeRead | None:
    """Получает спор по его ID."""
    dispute = await db.get(Dispute, dispute_id)
    return DisputeRead.model_validate(dispute) if dispute else None


async def update_dispute(
    db: AsyncSession, dispute_id: int, update_data: DisputeUpdate
) -> DisputeRead | None:
    """Обновляет данные спора (для админов)."""
    dispute = await db.get(Dispute, dispute_id)
    if not dispute:
        return None

    update_data_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_data_dict.items():
        setattr(dispute, key, value)

    try:
        async with db.begin():
            pass

        await db.refresh(dispute)
        return DisputeRead.model_validate(dispute)

    except Exception as e:
        # `async with db.begin()` уже выполнил rollback.
        logger.error(f"Error updating dispute ID {dispute_id}: {e}")
        raise
