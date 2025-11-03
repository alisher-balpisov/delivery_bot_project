from fastapi import APIRouter, HTTPException, status

from backend.src.auth.dependencies import RequireAdmin, RequireAllRoles, RequireShopOrCourier
from backend.src.common.enums import UserRole
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.disputes import service
from backend.src.schemas.dispute import DisputeCreate, DisputeResponse, DisputeUpdate

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый спор",
    description="Открывает новый спор по заказу. Доступно только магазинам и курьерам.",
)
async def create_new_dispute(
    dispute_in: DisputeCreate,
    current_user: RequireShopOrCourier,
    db: DbSession,
):
    """
    Создание нового спора по заказу.

    Только магазины и курьеры, связанные с заказом, могут открывать споры.
    """
    logger.info(
        f"User {current_user.id} ({current_user.role}) creating dispute for order {dispute_in.order_id}"
    )

    try:
        return await service.create_dispute(db=db, dispute_data=dispute_in, initiator=current_user)
    except ValueError as e:
        logger.warning(f"Validation error creating dispute: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{dispute_id}",
    response_model=DisputeResponse,
    summary="Получить спор по ID",
    description="Возвращает детали спора. Доступ только у участников спора и админов.",
)
async def get_dispute_details(
    dispute_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Получение деталей спора по ID.

    Доступ имеют:
    - Администраторы (все споры)
    - Магазин, связанный со спором
    - Курьер, связанный со спором
    """
    logger.debug(f"User {current_user.id} ({current_user.role}) requesting dispute {dispute_id}")

    dispute = await service.get_dispute_by_id(db=db, dispute_id=dispute_id)
    if not dispute:
        logger.warning(f"Dispute {dispute_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Спор не найден")

    # Проверка авторизации
    if current_user.role == UserRole.ADMIN:
        pass  # Админ может видеть все споры
    elif current_user.role == UserRole.SHOP:
        if not current_user.shop or dispute.shop_id != current_user.shop.id:
            logger.warning(
                f"Shop user {current_user.id} tried to access dispute {dispute_id} "
                f"from another shop"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому спору",
            )
    elif current_user.role == UserRole.COURIER:
        if not current_user.courier or dispute.courier_id != current_user.courier.id:
            logger.warning(
                f"Courier user {current_user.id} tried to access dispute {dispute_id} "
                f"from another courier"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому спору",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа",
        )

    logger.info(f"Dispute {dispute_id} returned to user {current_user.id}")
    return dispute


@router.patch(
    "/{dispute_id}",
    response_model=DisputeResponse,
    summary="Обновить спор",
    description="Обновляет данные спора. Доступно только администраторам.",
)
async def update_existing_dispute(
    dispute_id: int,
    dispute_in: DisputeUpdate,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Обновление спора (только для админов).

    Администратор может обновить:
    - Статус спора
    - Заметки администратора
    - Описание решения
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
