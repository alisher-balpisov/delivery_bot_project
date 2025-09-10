from backend.src.auth.user_auth import get_current_user, require_role
from backend.src.common.enums import UserRole
from backend.src.core.database import get_db
from backend.src.core.logging import get_logger
from backend.src.models.user import User
from backend.src.orders import service
from backend.src.schemas.order import OrderCreate, OrderCreateRequest, OrderRead, OrderUpdate
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = get_logger(__name__)


async def check_user_role(db: AsyncSession, telegram_id: int, required_role: UserRole) -> bool:
    """Проверить, имеет ли пользователь требуемую роль"""
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning(f"User {telegram_id} not found")
        return False
    if user.role != required_role and user.role != UserRole.admin:
        logger.warning(f"User {telegram_id} has role {user.role}, required {required_role}")
        return False
    return True


router = APIRouter()


@router.post("/", response_model=OrderRead, status_code=201)
async def create_new_order(
    order_in: OrderCreateRequest,
    current_user: User = Depends(require_role("shop")),
    db: AsyncSession = Depends(get_db),
):
    """
    Создание нового заказа.
    Доступно только магазинам.
    """
    logger.info(f"Order creation attempt by shop: telegram_id={current_user.telegram_id}")

    order_data = OrderCreate(**order_in.model_dump(), telegram_id=current_user.telegram_id)

    try:
        result = await service.create_order(db=db, order_data=order_data)
        logger.info(
            f"Order created successfully: id={result.id}, telegram_id={current_user.telegram_id}"
        )
        return result
    except Exception as e:
        logger.error(f"Order creation failed: {e!s}")
        raise HTTPException(status_code=400, detail=f"Не удалось создать заказ: {e!s}")


@router.get("/{order_id}", response_model=OrderRead)
async def get_order_details(
    order_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение деталей заказа по ID.
    Доступно авторизованным пользователям.
    """
    order = await service.get_order_by_id(db=db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Проверка доступа: магазины видят только свои заказы, курьеры - назначенные, админы все
    logger.info(
        f"Access check for order {order_id} by user {current_user.telegram_id}, role {current_user.role}"
    )
    if current_user.role == "shop":
        if not current_user.shop:
            logger.error(f"Shop user {current_user.telegram_id} has no shop relation")
            raise HTTPException(status_code=403, detail="Нет доступа к заказам")
        if order.shop_id != current_user.shop.id:
            raise HTTPException(status_code=403, detail="Нет доступа к этому заказу")
    elif current_user.role == "courier":
        if not current_user.courier:
            logger.error(f"Courier user {current_user.telegram_id} has no courier relation")
            raise HTTPException(status_code=403, detail="Нет доступа к заказам")
        if order.courier_id != current_user.courier.id:
            raise HTTPException(status_code=403, detail="Заказ не назначен вам")
    logger.info(f"Access granted for user {current_user.telegram_id} to order {order_id}")

    return order


@router.patch("/{order_id}", response_model=OrderRead)
async def update_existing_order(
    order_id: int,
    order_in: OrderUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновление существующего заказа.
    Магазины могут отменять свои заказы, курьеры изменять статус, админы любые изменения.
    """
    if not order_in.status:
        raise HTTPException(status_code=400, detail="Поддерживаются только обновления статуса")

    order = await service.get_order_by_id(db=db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Проверка доступа
    if current_user.role == "shop":
        # Магазины могут только отменять свои заказы в состоянии "новый"
        if order.shop_id != current_user.shop.id:
            raise HTTPException(status_code=403, detail="Нет доступа к этому заказу")
        if order_in.status != "cancelled":
            raise HTTPException(status_code=403, detail="Магазины могут только отменить заказ")
        if order.status != "new":
            raise HTTPException(status_code=400, detail="Можно отменить только новый заказ")

    elif current_user.role == "courier":
        # Курьеры могут обновлять только назначенные им заказы
        if order.courier_id != current_user.courier.id:
            raise HTTPException(status_code=403, detail="Заказ не назначен вам")

    # Изменение статуса для курьера требует заметки
    if (
        current_user.role == "courier"
        and order_in.status == "in_pickup"
        and not order_in.courier_notes
    ):
        raise HTTPException(status_code=400, detail="Требуется заметка о статусе для курьера")

    updated_order = await service.update_order_status(
        db=db,
        order_id=order_id,
        new_status=order_in.status,
        courier_notes=order_in.courier_notes,
    )

    if not updated_order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    return updated_order
