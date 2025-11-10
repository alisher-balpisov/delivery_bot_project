from fastapi import APIRouter, HTTPException, status

from backend.src.auth.dependencies import RequireAllRoles, RequireShop
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger

from . import service
from .exceptions import OrderException
from .schemas import (
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
    Создание нового заказа магазином.

    **Права доступа**: только магазины

    **Типы заказов**:
    - `regular`: обычный заказ, курьер назначается автоматически
    - `special`: специальный заказ с указанием конкретного курьера

    **Возвращаемые коды**:
    - `201`: заказ успешно создан
    - `400`: некорректные данные заказа или курьер не найден
    - `401`: пользователь не авторизован
    - `403`: пользователь не является магазином
    - `500`: внутренняя ошибка сервера
    """
    logger.info(
        f"Попытка создания заказа: магазин {current_user.shop}, "
        f"order_type={order_in.order_type}, special_type={order_in.special_type}"
    )

    try:
        order = await service.create_order(
            db=db,
            order_in=order_in,
            shop_id=current_user.shop.id,  # type: ignore
        )
        logger.info(f"Заказ order_id={order.id} успешно создан магазином {current_user.shop}")
        return order

    except ValueError as e:
        logger.warning(f"Ошибка валидации при создании заказа магазином {current_user.shop}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Некорректные данные заказа: {e!s}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при создании заказа магазином {current_user.shop}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при создании заказа",
        )


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    order_in: OrderUpdate,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Обновление существующего заказа.

    **Права на изменение по ролям**:
    - **Администратор**: может изменять любые поля любых заказов
    - **Магазин**: может только отменить свой заказ (status -> CANCELED)
    - **Курьер**: может изменять status, courier_notes, completion_notes своих заказов

    **Ограничения**:
    - Нельзя изменять заказы в финальных статусах (COMPLETED, CANCELED)
    - Каждая роль имеет строго определённый набор разрешённых операций

    **Возвращаемые коды**:
    - `200`: заказ успешно обновлён
    - `400`: некорректные данные обновления
    - `401`: пользователь не авторизован
    - `403`: недостаточно прав для обновления
    - `404`: заказ не найден
    - `500`: внутренняя ошибка сервера
    """
    logger.info(
        f"Попытка обновления заказа {order_id=}: пользователь {current_user}, "
        f"поля={list(order_in.model_dump(exclude_unset=True).keys())}"
    )

    try:
        updated_order = await service.update_order(db, order_id, order_in, current_user)
        logger.info(f"Заказ {order_id=} успешно обновлён пользователем {current_user} ")
        return updated_order

    except OrderException as e:
        logger.warning(
            f"Запрещённая операция обновления заказа {order_id=} "
            f"пользователем {current_user}: {e.detail}"
        )
        raise
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при обновлении заказа {order_id=} "
            f"пользователем {current_user}: {e!s}",
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
async def get_order_endpoint(
    order_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Получение детальной информации о заказе.

    **Права доступа**:
    - **Администратор**: доступ ко всем заказам с полной информацией
    - **Магазин**: доступ только к своим заказам
    - **Курьер**: доступ только к назначенным ему заказам

    **Форматы ответа** (зависят от роли):
    - Администратор получает полную информацию о магазине и курьере
    - Магазин видит информацию о курьере
    - Курьер видит информацию о магазине

    **Возвращаемые коды**:
    - `200`: заказ успешно получен
    - `401`: пользователь не авторизован
    - `403`: нет прав на просмотр этого заказа
    - `404`: заказ не найден
    - `500`: внутренняя ошибка сервера
    """
    logger.info(f"Получение заказа {order_id=} пользователем {current_user=}")

    try:
        response = await service.get_order(
            db=db,
            user_id=current_user.id,
            order_id=order_id,
        )
        logger.info(f"Заказ {order_id=} успешно получен пользователем {current_user}")
        return response
    except OrderException as e:
        logger.warning(
            f"Ошибка доступа при получении заказа {order_id=} "
            f"пользователем {current_user}: {e.detail}"
        )
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении заказа {order_id=}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось получить заказ"
        )
