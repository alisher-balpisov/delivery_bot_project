from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.disputes import service
from src.schemas.dispute import DisputeCreate, DisputeRead, DisputeUpdate

router = APIRouter()


@router.post("/", response_model=DisputeRead, status_code=201)
async def create_new_dispute(dispute_in: DisputeCreate, db: AsyncSession = Depends(get_db)):
    """
    Создание нового спора по заказу.
    """
    # TODO: Добавить проверку авторизации пользователя (кто создает спор)
    try:
        return await service.create_dispute(db=db, dispute_data=dispute_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{dispute_id}", response_model=DisputeRead)
async def get_dispute_details(dispute_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получение деталей спора по ID.
    """
    dispute = await service.get_dispute_by_id(db=db, dispute_id=dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return dispute


@router.patch("/{dispute_id}", response_model=DisputeRead)
async def update_existing_dispute(
    dispute_id: int, dispute_in: DisputeUpdate, db: AsyncSession = Depends(get_db)
):
    """
    Обновление спора (для админов).
    """
    updated_dispute = await service.update_dispute(
        db=db, dispute_id=dispute_id, update_data=dispute_in
    )
    if not updated_dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return updated_dispute
