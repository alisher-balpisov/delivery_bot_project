from backend.src.auth.dependencies import RequireAdmin, RequireAllRoles
from backend.src.common.enums import UserRole
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.disputes import service
from backend.src.schemas.dispute import DisputeCreate, DisputeRead, DisputeUpdate
from fastapi import APIRouter, HTTPException, status

logger = get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=DisputeRead, status_code=201)
async def create_new_dispute(
    dispute_in: DisputeCreate,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Создание нового спора по заказу.
    """
    if current_user.role not in [UserRole.SHOP, UserRole.COURIER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только магазины и курьеры могут открывать споры",
        )
    # The role of the creator is now reliably taken from the token
    dispute_in.created_by_role = current_user.role
    try:
        return await service.create_dispute(db=db, dispute_data=dispute_in, initiator=current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{dispute_id}", response_model=DisputeRead)
async def get_dispute_details(
    dispute_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Получение деталей спора по ID.
    """
    dispute = await service.get_dispute_by_id(db=db, dispute_id=dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")

    # Authorization logic using the trusted current_user from the JWT
    if current_user.role == UserRole.ADMIN:
        pass  # Admin can see all disputes
    elif current_user.role == UserRole.SHOP:
        if not current_user.shop or dispute.shop_id != current_user.shop.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому спору"
            )
    elif current_user.role == UserRole.COURIER:
        if not current_user.courier or dispute.courier_id != current_user.courier.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому спору"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав доступа"
        )

    return dispute


@router.patch("/{dispute_id}", response_model=DisputeRead)
async def update_existing_dispute(
    dispute_id: int,
    dispute_in: DisputeUpdate,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Обновление спора (только для админов).
    """
    updated_dispute = await service.update_dispute(
        db=db, dispute_id=dispute_id, update_data=dispute_in
    )
    if not updated_dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    return updated_dispute
