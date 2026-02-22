from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.src.common.enums import DisputeStatus, OrderStatus, UserRole
from backend.src.core.logging import get_logger
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
from backend.src.models.user import User

from .exceptions import DisputeAccessDenied, DisputeActionError
from .schemas import (
    DisputeCardResponse,
    DisputeCreate,
    DisputeResponse,
    DisputesListResponse,
    DisputeUpdate,
)

logger = get_logger(__name__)


async def get_disputes(
    db: AsyncSession,
    page: int = 1,
    limit: int = 10,
    status: DisputeStatus | None = None,
) -> DisputesListResponse:
    """
    Получает список споров с пагинацией и фильтрацией.

    Args:
        db: Сессия базы данных
        page: Номер страницы (начиная с 1)
        limit: Количество элементов на странице
        status: Фильтр по статусу спора (опционально)

    Returns:
        DisputesListResponse с элементами и метаданными пагинации
    """
    logger.info(f"Fetching disputes: page={page}, limit={limit}, status={status}")

    # Базовый запрос с загрузкой связанных данных
    query = (
        select(Dispute)
        .options(
            selectinload(Dispute.order).selectinload(Order.shop),
            selectinload(Dispute.order).selectinload(Order.courier),
            selectinload(Dispute.opened_by_user),
        )
        .order_by(Dispute.created_at.desc())
    )

    # Применяем фильтр по статусу, если указан
    if status:
        query = query.where(Dispute.status == status)

    # Получаем общее количество записей для пагинации
    count_query = select(func.count()).select_from(Dispute)
    if status:
        count_query = count_query.where(Dispute.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Применяем пагинацию
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Выполняем запрос
    result = await db.execute(query)
    disputes = result.scalars().all()

    # Преобразуем в схему ответа
    items = []
    for dispute in disputes:
        try:
            card = DisputeCardResponse.from_dispute(dispute)
            items.append(card)
        except ValueError as e:
            logger.warning(f"Skipping dispute {dispute.id} due to data error: {e}")
            continue

    logger.info(f"Found {len(items)} disputes (total: {total})")

    return DisputesListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=(total + limit - 1) // limit if limit > 0 else 1,
    )


async def create_dispute(
    db: AsyncSession, dispute_data: DisputeCreate, initiator: User
) -> DisputeResponse:
    """
    Создает новый спор по заказу.
    """
    logger.info(f"User {initiator.id} creating dispute for order {dispute_data.order_id}")

    query = select(Order).where(Order.id == dispute_data.order_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()

    if not order:
        logger.warning(f"Order {dispute_data.order_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    if order.status not in OrderStatus.allowed_statuses_for_create_dispute():
        raise DisputeActionError(f"Нельзя открыть спор для заказа в статусе {order.status}")

    user_shop_id = getattr(initiator.shop, "id", None) if initiator.shop else None
    user_courier_id = getattr(initiator.courier, "id", None) if initiator.courier else None

    is_shop_owner = user_shop_id and user_shop_id == order.shop_id
    is_courier_owner = user_courier_id and user_courier_id == order.courier_id

    if not (is_shop_owner or is_courier_owner):
        raise DisputeAccessDenied("Вы можете открывать споры только по своим заказам")

    # 4. Проверка на наличие активного спора
    active_dispute_query = select(Dispute).where(
        Dispute.order_id == dispute_data.order_id,
        Dispute.status.in_(DisputeStatus.active_statuses()),
    )
    active_dispute_result = await db.execute(active_dispute_query)
    if active_dispute_result.scalar_one_or_none():
        logger.warning(f"Active dispute for order {dispute_data.order_id} already exists.")
        raise DisputeActionError("По этому заказу уже есть активный спор")

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

    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating dispute: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка при создании спора"
        )
        await db.rollback()
        logger.error(f"Error creating dispute: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка при создании спора"
        )

    # 5. Формирование ответа
    return DisputeResponse(
        **new_dispute.__dict__,
        courier_id=order.courier_id,
        courier_full_name=order.courier.full_name if order.courier else None,
        shop_id=order.shop_id,
        shop_name=order.shop.name if order.shop else None,
        opened_by_role=initiator.role,
    )


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
            selectinload(Dispute.order).selectinload(Order.shop),
            selectinload(Dispute.order).selectinload(Order.courier),
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

    opened_by_user = dispute.opened_by_user
    opened_by_role = opened_by_user.role if opened_by_user else UserRole.GUEST

    return DisputeResponse(
        id=dispute.id,
        order_id=dispute.order_id,
        description=dispute.description,
        courier_id=dispute.order.courier_id,
        courier_full_name=dispute.order.courier.full_name if dispute.order.courier else None,
        shop_id=dispute.order.shop_id,
        shop_name=dispute.order.shop.name if dispute.order.shop else "отсутствует",
        status=dispute.status,
        opened_by_role=opened_by_role,
        resolution_comment=dispute.resolution_comment,
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
            selectinload(Dispute.order).selectinload(Order.shop),
            selectinload(Dispute.order).selectinload(Order.courier),
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

        opened_by_user = dispute.opened_by_user
        opened_by_role = opened_by_user.role if opened_by_user else UserRole.GUEST

        return DisputeResponse(
            id=dispute.id,
            order_id=dispute.order_id,
            description=dispute.description,
            courier_id=dispute.order.courier_id,
            courier_full_name=dispute.order.courier.full_name if dispute.order.courier else None,
            shop_id=dispute.order.shop_id,
            shop_name=dispute.order.shop.name if dispute.order.shop else "отсутствует",
            status=dispute.status,
            opened_by_role=opened_by_role,
            resolution_comment=dispute.resolution_comment,
            created_at=dispute.created_at,
            resolved_at=dispute.resolved_at,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating dispute ID {dispute_id}: {e}")
        raise


async def get_user_disputes(
    db: AsyncSession,
    user: User,
    page: int = 1,
    limit: int = 10,
    status: DisputeStatus | None = None,
) -> DisputesListResponse:
    """
    Получает список споров для конкретного пользователя (магазина или курьера).
    """
    logger.info(
        f"Fetching disputes for user {user.id}: page={page}, limit={limit}, status={status}"
    )

    # Базовый запрос
    query = (
        select(Dispute)
        .options(
            selectinload(Dispute.order).selectinload(Order.shop),
            selectinload(Dispute.order).selectinload(Order.courier),
            selectinload(Dispute.opened_by_user),
        )
        .order_by(Dispute.created_at.desc())
    )

    # Фильтрация по роли пользователя
    if user.role == UserRole.SHOP:
        query = query.join(Order).where(Order.shop_id == user.shop.id)
    elif user.role == UserRole.COURIER:
        query = query.join(Order).where(Order.courier_id == user.courier.id)
    else:
        # Для других ролей (кроме админа, который использует другой метод)
        # возвращаем пустой список или фильтруем по открывшему
        query = query.where(Dispute.opened_by_user_id == user.id)

    # Применяем фильтр по статусу, если указан
    if status:
        query = query.where(Dispute.status == status)

    # Подсчет общего количества
    count_query = select(func.count()).select_from(Dispute)
    if user.role == UserRole.SHOP:
        count_query = count_query.join(Order).where(Order.shop_id == user.shop.id)
    elif user.role == UserRole.COURIER:
        count_query = count_query.join(Order).where(Order.courier_id == user.courier.id)
    else:
        count_query = count_query.where(Dispute.opened_by_user_id == user.id)

    if status:
        count_query = count_query.where(Dispute.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Пагинация
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Выполнение
    result = await db.execute(query)
    disutes_objs = result.scalars().all()

    items = []
    for d in disutes_objs:
        try:
            items.append(DisputeCardResponse.from_dispute(d))
        except ValueError as e:
            logger.warning(f"Skipping dispute {d.id} due to data error: {e}")
            continue

    return DisputesListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=(total + limit - 1) // limit if limit > 0 else 1,
    )
