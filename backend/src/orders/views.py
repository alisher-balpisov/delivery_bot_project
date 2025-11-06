from fastapi import APIRouter, HTTPException, status

from backend.src.auth.dependencies import RequireAllRoles, RequireShop
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.orders import service
from backend.src.orders.exceptions import OrderException
from backend.src.schemas.order import (
    OrderCreateRequest,
    OrderResponse,
    OrderResponseForAdmin,
    OrderResponseForCourier,
    OrderResponseForShop,
    OrderUpdate,
)

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_in: OrderCreateRequest,
    current_user: RequireShop,
    db: DbSession,
):
    """
    Создание нового заказа.
    """
    logger.info(
        f"Создание заказа для магазина {current_user.shop}, order_type={order_in.order_type}"
    )
    try:
        result = await service.create_order(db=db, order_in=order_in, shop_id=current_user.shop.id)
        logger.info(f"Заказ успешно создан: order_id={result.id} для магазина {current_user.shop}")
        return result
    except ValueError as e:
        logger.error(
            f"Ошибка валидации при создании заказа для пользователя {current_user.id}: {e!s}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Некорректные данные заказа: {e!s}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Создание заказа не удалось для пользователя {current_user}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при создании заказа",
        )


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_existing_order(
    order_id: int,
    order_in: OrderUpdate,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Обновление существующего заказа.

    Права на изменение:
    - **Админ**: может изменять любые поля.
    - **Магазин**: может только отменить заказ (`status: CANCELED`).
    - **Курьер**: может изменять `status`, `courier_notes`, `completion_notes`.

    Возвращает:
    - `200 OK`: при успешном обновлении.
    - `404 Not Found`: если заказ не найден.
    - `403 Forbidden`: если у пользователя нет прав на обновление.
    - `500 Internal Server Error`: при непредвиденных ошибках.
    """
    try:
        updated_order = await service.update_order(db, order_id, order_in, current_user)
        logger.info(f"Заказ {order_id} успешно обновлен пользователем {current_user.id}")
        return updated_order
    except OrderException as e:
        logger.warning(
            f"Ошибка обновления заказа {order_id} пользователем {current_user.id}: {e.detail}"
        )
        raise e
    except Exception as e:
        logger.error(
            f"Непредвиденная ошибка при обновлении заказа {order_id} "
            f"пользователем {current_user.id}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при обновлении заказа",
        )


@router.get(
    "/{order_id}",
    response_model=OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier,
)
async def get_order(
    order_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Получение деталей заказа по ID.
    """
    logger.info(f"Получение заказа {order_id=} пользователем {current_user}")

    try:
        response = await service.get_order(
            db=db,
            user_id=current_user.id,
            order_id=order_id,
        )
        logger.info(f"Заказ {order_id=} успешно получен пользователем {current_user}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении заказа {order_id=}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось получить заказ"
        )
