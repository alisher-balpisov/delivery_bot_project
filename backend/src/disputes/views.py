from fastapi import APIRouter, HTTPException, Query, status

from backend.src.auth.dependencies import RequireAdmin, RequireAllRoles, RequireShopOrCourier
from backend.src.common.enums import DisputeStatus
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger

from . import service
from .exceptions import DisputeAccessDenied, DisputeActionError
from .schemas import DisputeCreate, DisputeResponse, DisputesListResponse, DisputeUpdate

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/admin/disputes",
    response_model=DisputesListResponse,
    summary="Получить список споров (для администраторов)",
    description="Возвращает список всех споров с пагинацией и фильтрацией по статусу.",
)
async def get_disputes_list(
    current_user: RequireAdmin,
    db: DbSession,
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(10, ge=1, le=50, description="Количество элементов на странице"),
    status: DisputeStatus | None = Query(None, description="Фильтр по статусу спора"),
):
    """
    Получение списка споров для администраторов.

    Возвращает пагинированный список споров с информацией о заказах,
    магазинах и курьерах. Поддерживает фильтрацию по статусу.
    """
    logger.info(
        f"Admin {current_user.id} requesting disputes list: page={page}, limit={limit}, status={status}"
    )

    disputes_list = await service.get_disputes(
        db=db,
        page=page,
        limit=limit,
        status=status,
    )

    logger.info(f"Returning {len(disputes_list.items)} disputes for admin {current_user.id}")
    return disputes_list


@router.post(
    "/",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый спор",
    description="Открывает новый спор по заказу. Доступно только магазинам и курьерам.",
)
async def create_dispute(
    dispute_in: DisputeCreate,
    current_user: RequireShopOrCourier,
    db: DbSession,
):
    """
    Создание нового спора по заказу.
    Только магазины и курьеры, связанные с заказом, могут открывать споры.
    """
    logger.info(
        f"User {current_user.id} attempting to create dispute for order {dispute_in.order_id}"
    )
    try:
        dispute = await service.create_dispute(
            db=db, dispute_data=dispute_in, initiator=current_user
        )
        logger.info(f"Dispute for order {dispute_in.order_id} created successfully.")
        return dispute
    except ValueError as e:
        logger.warning(f"Validation error while creating dispute: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DisputeActionError as e:
        logger.warning(f"Action error while creating dispute for order {dispute_in.order_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DisputeAccessDenied as e:
        logger.warning(
            f"Access denied for user {current_user.id} on order {dispute_in.order_id}: {e}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get(
    "/{dispute_id}",
    response_model=DisputeResponse,
    summary="Получить спор по ID",
    description="Возвращает детали спора. Доступ только у участников спора и админов.",
)
async def get_dispute(
    dispute_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Получение деталей спора по ID.

    Доступ имеют администраторы и участники спора (магазин или курьер).
    """
    logger.debug(f"User {current_user.id} requesting dispute {dispute_id}")
    try:
        dispute = await service.get_dispute_by_id(
            db=db, dispute_id=dispute_id, current_user=current_user
        )
        if not dispute:
            logger.warning(f"Dispute {dispute_id} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Спор не найден")

        logger.info(f"Dispute {dispute_id} returned to user {current_user.id}")
        return dispute
    except DisputeAccessDenied as e:
        logger.warning(f"Access denied for user {current_user.id} on dispute {dispute_id}: {e}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        logger.error(f"Data integrity error for dispute {dispute_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера",
        )


@router.patch(
    "/{dispute_id}",
    response_model=DisputeResponse,
    summary="Обновить спор",
    description="Обновляет данные спора. Доступно только администраторам.",
)
async def update_dispute(
    dispute_id: int,
    dispute_in: DisputeUpdate,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Обновление спора (только для админов).

    Администратор может обновить статус спора и добавить заметки о решении.
    """
    logger.info(f"Admin {current_user.id} updating dispute {dispute_id}")

    updated_dispute = await service.update_dispute(
        db=db, dispute_id=dispute_id, update_data=dispute_in
    )
    if not updated_dispute:
        logger.warning(f"Dispute {dispute_id} not found for update")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Спор не найден")

    logger.info(f"Dispute {dispute_id} successfully updated by admin {current_user.id}")
    return updated_dispute
