from backend.src.auth.dependencies import RequireAllRoles, RequireShop
from backend.src.common.enums import UserRole
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.orders import service
from backend.src.schemas.order import OrderCreate, OrderCreateRequest, OrderRead, OrderUpdate
from fastapi import APIRouter, HTTPException, status

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=OrderRead, status_code=201)
async def create_new_order(
    order_in: OrderCreateRequest,
    current_user: RequireShop,
    db: DbSession,
):
    """
    Создание нового заказа. Доступно только магазинам.
    ID магазина берется из профиля аутентифицированного пользователя.
    """
    logger.info(f"Order creation attempt by user ID: {current_user.id}")
    if not current_user.shop:
        logger.error(f"User {current_user.id} with role SHOP has no associated shop profile.")
        raise HTTPException(
            status_code=403, detail="Профиль магазина не найден для вашего аккаунта"
        )

    # The shop_id is now taken from the authenticated user, not the request body.
    order_data = OrderCreate(**order_in.model_dump(), shop_id=current_user.shop.id)

    try:
        result = await service.create_order(db=db, order_data=order_data)
        logger.info(
            f"Order created successfully: id={result.id} for shop_id={current_user.shop.id}"
        )
        return result
    except Exception as e:
        logger.error(f"Order creation failed for user {current_user.id}: {e!s}")
        raise HTTPException(status_code=400, detail=f"Не удалось создать заказ: {e!s}")


@router.get("/{order_id}", response_model=OrderRead)
async def get_order_details(
    order_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Получение деталей заказа по ID.
    Доступно авторизованным пользователям с проверкой прав.
    """
    order = await service.get_order_by_id(db=db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Authorization check using the trusted current_user from the JWT
    logger.info(
        f"Access check for order {order_id} by user {current_user.id}, role {current_user.role}"
    )
    if current_user.role == UserRole.ADMIN:
        pass  # Admin sees all
    elif current_user.role == UserRole.SHOP:
        if not current_user.shop or order.shop_id != current_user.shop.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому заказу"
            )
    elif current_user.role == UserRole.COURIER:
        if not current_user.courier or order.courier_id != current_user.courier.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Заказ не назначен вам"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав доступа"
        )

    logger.info(f"Access granted for user {current_user.id} to order {order_id}")
    return order


@router.patch("/{order_id}", response_model=OrderRead)
async def update_existing_order(
    order_id: int,
    order_in: OrderUpdate,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Обновление существующего заказа.
    """
    updated_order = await service.update_order(db, order_id, order_in, current_user)
    if not updated_order:
        # The service layer raises specific HTTP exceptions
        raise HTTPException(status_code=500, detail="Не удалось обновить заказ")
    return updated_order
