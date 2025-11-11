from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.src.common.enums import DisputeStatus, UserRole
from backend.src.core.logging import get_logger
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
from backend.src.models.user import User

from .exceptions import DisputeAccessDenied, DisputeActionError
from .schemas import DisputeCreate, DisputeResponse, DisputeUpdate

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

    Raises:
        ValueError: Если заказ не найден.
        DisputeActionError: Если спор по этому заказу уже существует.
        DisputeAccessDenied: Если у пользователя нет прав на создание спора.
    """
    logger.info(f"User {initiator.id} creating dispute for order {dispute_data.order_id}")

    result = await db.execute(select(Order).where(Order.id == dispute_data.order_id))
    order = result.scalar_one_or_none()
    if not order:
        logger.warning(f"Order {dispute_data.order_id} not found for dispute creation.")
        raise ValueError("Заказ не найден")

    # Проверка авторизации - может создать только магазин или курьер, связанный с заказом
    is_shop = initiator.shop and initiator.shop.id == order.shop_id
    is_courier = initiator.courier and initiator.courier.id == order.courier_id
    if not (is_shop or is_courier):
        raise DisputeAccessDenied("Вы можете открывать споры только по своим заказам")

    # Проверка на существующий спор по этому заказу
    existing_dispute_result = await db.execute(
        select(Dispute).where(Dispute.order_id == dispute_data.order_id)
    )
    if existing_dispute_result.scalar_one_or_none():
        raise DisputeActionError("Спор по этому заказу уже существует")

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

        return DisputeResponse(
            id=new_dispute.id,
            order_id=new_dispute.order_id,
            description=new_dispute.description,
            courier_id=order.courier_id,
            shop_id=order.shop_id,
            status=new_dispute.status,
            created_by_role=initiator.role,
            resolution_notes=new_dispute.resolution_comment,
            created_at=new_dispute.created_at,
            resolved_at=new_dispute.resolved_at,
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating dispute for order {dispute_data.order_id}: {e}")
        raise


async def get_dispute_by_id(
    db: AsyncSession, dispute_id: int, current_user: User
) -> DisputeResponse | None:
    """
    Получает спор по ID с проверкой прав доступа.

    Args:
        db: Сессия базы данных.
        dispute_id: ID спора.
        current_user: Пользователь, запрашивающий спор.

    Raises:
        DisputeAccessDenied: Если у пользователя нет прав на просмотр спора.
        ValueError: При ошибке целостности данных.
    """
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

    # Проверка авторизации
    if current_user.role != UserRole.ADMIN:
        is_shop_participant = (
            current_user.role == UserRole.SHOP
            and current_user.shop
            and current_user.shop.id == dispute.order.shop_id
        )
        is_courier_participant = (
            current_user.role == UserRole.COURIER
            and current_user.courier
            and current_user.courier.id == dispute.order.courier_id
        )
        if not (is_shop_participant or is_courier_participant):
            raise DisputeAccessDenied("Нет доступа к этому спору")

    # Проверка целостности данных
    if not dispute.order or not dispute.order.courier_id:
        logger.error(f"Data integrity error: Dispute {dispute_id} has incomplete order data.")
        raise ValueError("Ошибка целостности данных, связанная со спором.")

    created_by_role = dispute.opened_by_user.role if dispute.opened_by_user else UserRole.GUEST

    return DisputeResponse(
        id=dispute.id,
        order_id=dispute.order_id,
        description=dispute.description,
        courier_id=dispute.order.courier_id,
        shop_id=dispute.order.shop_id,
        status=dispute.status,
        created_by_role=created_by_role,
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

    for key, value in update_data_dict.items():
        model_key = "resolution_comment" if key == "resolution_notes" else key
        if hasattr(dispute, model_key):
            setattr(dispute, model_key, value)

    try:
        await db.commit()
        await db.refresh(dispute)

        # Проверка целостности данных
        if not dispute.order or not dispute.order.courier_id:
            logger.error(f"Data integrity error: Dispute {dispute_id} has incomplete order data.")
            raise ValueError("Ошибка целостности данных, связанная со спором.")

        created_by_role = dispute.opened_by_user.role if dispute.opened_by_user else UserRole.GUEST

        return DisputeResponse(
            id=dispute.id,
            order_id=dispute.order_id,
            description=dispute.description,
            courier_id=dispute.order.courier_id,
            shop_id=dispute.order.shop_id,
            status=dispute.status,
            created_by_role=created_by_role,
            resolution_notes=dispute.resolution_comment,
            created_at=dispute.created_at,
            resolved_at=dispute.resolved_at,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating dispute ID {dispute_id}: {e}")
        raise
