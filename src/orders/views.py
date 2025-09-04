from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.orders import service
from src.schemas.order import OrderCreate, OrderRead, OrderUpdate

router = APIRouter()


@router.post("/", response_model=OrderRead, status_code=201)
async def create_new_order(order_in: OrderCreate, db: AsyncSession = Depends(get_db)):
    """
    Создание нового заказа.
    """
    return await service.create_order(db=db, order_data=order_in)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order_details(order_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получение деталей заказа по ID.
    """
    order = await service.get_order_by_id(db=db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderRead)
async def update_existing_order(
    order_id: int, order_in: OrderUpdate, db: AsyncSession = Depends(get_db)
):
    """
    Обновление заказа (например, смена статуса).
    """
    updated_order = await service.update_order(db=db, order_id=order_id, update_data=order_in)
    if not updated_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return updated_order
