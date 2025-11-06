from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.src.common.enums import DisputeStatus, UserRole
from backend.src.core.logging import get_logger
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
from backend.src.models.user import User
from backend.src.schemas.dispute import DisputeCreate, DisputeResponse, DisputeUpdate

logger = get_logger(__name__)


async def create_dispute(
    db: AsyncSession, dispute_data: DisputeCreate, initiator: User
) -> DisputeResponse:
    """
    Создает новый спор по заказу.

    Args:
        db: Сессия базы данных.
        dispute_data: Данные для создания спора.
        initiator: Пользователь, который создает спор (из токена).
    """
    logger.info(f"User {initiator.id} creating dispute for order {dispute_data.order_id}")

    result = await db.execute(select(Order).where(Order.id == dispute_data.order_id))
    order = result.scalar_one_or_none()
    if not order:
        logger.warning(f"Order {dispute_data.order_id} not found.")
        raise ValueError("Заказ не найден")

    # Проверка авторизации - может создать только магазин или курьер, связанный с заказом
    is_shop = initiator.shop and initiator.shop.id == order.shop_id
    is_courier = initiator.courier and initiator.courier.id == order.courier_id
    if not (is_shop or is_courier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы можете открывать споры только по своим заказам",
        )

    # Проверка на существующий спор по этому заказу
    existing_dispute = await db.execute(
        select(Dispute).where(Dispute.order_id == dispute_data.order_id)
    )
    if existing_dispute.scalar_one_or_none():
        raise ValueError("Спор по этому заказу уже существует")

    new_dispute = Dispute(
        order_id=dispute_data.order_id,
        description=dispute_data.description,
        opened_by_user_id=initiator.id,
        status=DisputeStatus.PENDING_REVIEW,
    )

    try:
        db.add(new_dispute)
        await db.commit()
        await db.refresh(new_dispute)

        logger.info(f"Dispute created successfully with ID {new_dispute.id}")

        # Возвращаем DisputeResponse с необходимыми полями
        return DisputeResponse(
            id=new_dispute.id,
            order_id=new_dispute.order_id,
            description=new_dispute.description,
            courier_id=order.courier_id,
            shop_id=order.shop_id,
            status=new_dispute.status,
            created_by_role=initiator.role,
            admin_notes=None,
            resolution_notes=new_dispute.resolution_comment,
            created_at=new_dispute.created_at,
            resolved_at=new_dispute.resolved_at,
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating dispute: {e}")
        raise


async def get_dispute(db: AsyncSession, dispute_id: int) -> DisputeResponse | None:
    """Получает спор по его ID с полной информацией."""
    result = await db.execute(
        select(Dispute)
        .options(
            selectinload(Dispute.order),
            selectinload(Dispute.opened_by_user),
            selectinload(Dispute.fined_user),
        )
        .where(Dispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        return None

    # Получаем роль создателя спора
    created_by_role = dispute.opened_by_user.role if dispute.opened_by_user else UserRole.GUEST

    # Проверка целостности данных - спор должен иметь курьера
    if not dispute.order.courier_id:
        logger.error(f"Data integrity error: Dispute {dispute_id} has no courier_id")
        raise ValueError("Ошибка данных: спор существует для заказа без курьера")

    return DisputeResponse(
        id=dispute.id,
        order_id=dispute.order_id,
        description=dispute.description,
        courier_id=dispute.order.courier_id,
        shop_id=dispute.order.shop_id,
        status=dispute.status,
        created_by_role=created_by_role,
        admin_notes=None,  # Это поле не существует в модели, но есть в схеме
        resolution_notes=dispute.resolution_comment,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at,
    )


async def update_dispute(
    db: AsyncSession, dispute_id: int, update_data: DisputeUpdate
) -> DisputeResponse | None:
    """Обновляет данные спора (для админов)."""
    result = await db.execute(
        select(Dispute)
        .options(
            selectinload(Dispute.order),
            selectinload(Dispute.opened_by_user),
        )
        .where(Dispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        return None

    update_data_dict = update_data.model_dump(exclude_unset=True)

    # Маппинг полей схемы на поля модели
    field_mapping = {
        "resolution_notes": "resolution_comment",
        # admin_notes не существует в модели, игнорируем его
    }

    for key in update_data_dict:
        value = update_data_dict[key]
        if key == "admin_notes":
            continue  # Это поле не существует в модели

        # Используем маппинг, если он есть
        model_key = field_mapping.get(key, key)
        setattr(dispute, model_key, value)

    try:
        await db.commit()
        await db.refresh(dispute)

        created_by_role = dispute.opened_by_user.role if dispute.opened_by_user else UserRole.GUEST

        # Проверка целостности данных - спор должен иметь курьера
        if not dispute.order.courier_id:
            logger.error(f"Data integrity error: Dispute {dispute_id} has no courier_id")
            raise ValueError("Ошибка данных: спор существует для заказа без курьера")

        return DisputeResponse(
            id=dispute.id,
            order_id=dispute.order_id,
            description=dispute.description,
            courier_id=dispute.order.courier_id,
            shop_id=dispute.order.shop_id,
            status=dispute.status,
            created_by_role=created_by_role,
            admin_notes=None,
            resolution_notes=dispute.resolution_comment,
            created_at=dispute.created_at,
            resolved_at=dispute.resolved_at,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating dispute ID {dispute_id}: {e}")
        raise
