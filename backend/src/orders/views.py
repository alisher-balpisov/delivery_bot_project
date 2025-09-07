from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_current_shop_telegram, get_current_user
from src.core.database import get_db
from src.core.logging import get_logger
from src.models.user import User
from src.orders import service
from src.schemas.order import OrderCreate, OrderRead, OrderUpdate

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=OrderRead, status_code=201)
async def create_new_order(
    order_in: OrderCreate,
    current_user: User = Depends(get_current_shop_telegram),
    db: AsyncSession = Depends(get_db),
):
    """
    Создание нового заказа.
    Использует telegram_id из тела запроса для аутентификации пользователя.
    """
    logger.info(f"DEBUG: Вызван create_new_order для товара с telegram_id={order_in.telegram_id}")

    # Убедиться, что заказ принадлежит этому магазину
    if order_in.shop_id != current_user.id:
        logger.warning(
            f"DEBUG: Попытка создать заказ для другого магазина: order.shop_id={order_in.shop_id}, user.id={current_user.id}"
        )
        raise HTTPException(status_code=403, detail="Невозможно создать заказ для другого магазина")

    result = await service.create_order(db=db, order_data=order_in)
    logger.info(f"DEBUG: Создан заказ {result.id} для пользователя {current_user.id}")
    return result


@router.get("/{order_id}", response_model=OrderRead)
async def get_order_details(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение деталей заказа по ID.
    """
    order = await service.get_order_by_id(db=db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Проверить права доступа
    if current_user.role == "shop" and order.shop_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    if current_user.role == "courier" and order.courier_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    return order


@router.patch("/{order_id}", response_model=OrderRead)
async def update_existing_order(
    order_id: int, order_in: OrderUpdate, db: AsyncSession = Depends(get_db)
):
    if order_in.status:
        updated_order = await service.update_order_status(
            db=db,
            order_id=order_id,
            new_status=order_in.status,
            courier_notes=order_in.courier_notes,
        )
    else:
        raise HTTPException(status_code=400, detail="Поддерживаются только обновления статуса")

    if not updated_order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return updated_order
