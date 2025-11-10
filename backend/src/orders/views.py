from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as status_code

from backend.src.auth.dependencies import RequireAllRoles, RequireCourier, RequireShop
from backend.src.common.constants import PaginatedResponse
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger

from . import service
from .exceptions import OrderException
from .schemas import (
    OrderCompleteRequest,
    OrderCreateRequest,
    OrderListFilters,
    OrderListItemForAdmin,
    OrderListItemForCourier,
    OrderListItemForShop,
    OrderResponse,
    OrderResponseForAdmin,
    OrderResponseForCourier,
    OrderResponseForShop,
    OrderStatus,
    OrderUpdate,
)

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=OrderResponse, status_code=status_code.HTTP_201_CREATED)
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
            status_code=status_code.HTTP_400_BAD_REQUEST,
            detail=f"Некорректные данные заказа: {e!s}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при создании заказа магазином {current_user.shop}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status_code.HTTP_500_INTERNAL_SERVER_ERROR,
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
            status_code=status_code.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при обновлении заказа",
        )


@router.put("/{order_id}/complete", response_model=OrderResponse)
async def complete_order(
    order_id: int,
    request: OrderCompleteRequest,
    current_user: RequireCourier,
    db: DbSession,
):
    """
    Завершение заказа с загрузкой фото-отчета.

    **Права доступа**: только курьеры, назначенные на заказ

    **Требования**:
    - Заказ должен быть в статусе DELIVERING или SEMI_COMPLETED
    - Курьер должен быть назначен на этот заказ
    - Необходимо предоставить ID фото-отчета из Telegram

    **Результат**:
    - Статус заказа меняется на COMPLETED
    - Сохраняется photo_report_id
    - Устанавливается время завершения (completed_at)

    **Возвращаемые коды**:
    - `200`: заказ успешно завершён
    - `400`: некорректные данные
    - `401`: пользователь не авторизован
    - `403`: недостаточно прав (не курьер или не назначен на заказ)
    - `404`: заказ не найден
    - `500`: внутренняя ошибка сервера
    """
    logger.info(
        f"Попытка завершения заказа {order_id=} курьером {current_user.courier} "
        f"с фото-отчетом photo_report_id={request.photo_report_id}"
    )

    try:
        completed_order = await service.complete_order(
            db=db,
            order_id=order_id,
            photo_report_id=request.photo_report_id,
            current_user=current_user,
        )
        logger.info(f"Заказ {order_id=} успешно завершён курьером {current_user.courier}")
        return completed_order

    except OrderException as e:
        logger.warning(
            f"Ошибка завершения заказа {order_id=} курьером {current_user.courier}: {e.detail}"
        )
        raise
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при завершении заказа {order_id=} "
            f"курьером {current_user.courier}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status_code.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при завершении заказа",
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
            status_code=status_code.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось получить заказ",
        )


@router.get(
    "/history",
    response_model=PaginatedResponse[
        OrderListItemForAdmin | OrderListItemForShop | OrderListItemForCourier
    ],
)
async def get_orders_history(
    current_user: RequireAllRoles,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status: OrderStatus | None = None,
    shop_id: int | None = None,
    courier_id: int | None = None,
    current: bool | None = None,
):
    """
    Получение истории заказов с пагинацией и фильтрами.

    **Права доступа по ролям**:

    **Магазин**:
    - Видит только свои заказы
    - Доступные фильтры: `status`, `current`
    - Не может использовать `shop_id`, `courier_id`

    **Курьер**:
    - Видит только назначенные ему заказы
    - Доступные фильтры: `status`, `current`
    - Не может использовать `shop_id`, `courier_id`

    **Администратор**:
    - Видит все заказы
    - Доступные фильтры: `status`, `shop_id`, `courier_id`, `current`

    **Параметры запроса**:
    - `page`: Номер страницы (по умолчанию 1)
    - `limit`: Количество элементов на странице (1-100, по умолчанию 20)
    - `status`: Фильтр по статусу заказа
    - `shop_id`: Фильтр по ID магазина (только для админа)
    - `courier_id`: Фильтр по ID курьера (только для админа)
    - `current`: true - только активные заказы, false - только завершённые

    **Примеры запросов**:
    - `/orders/history` - первая страница всех доступных заказов
    - `/orders/history?page=2&limit=50` - вторая страница по 50 заказов
    - `/orders/history?status=completed` - только завершённые заказы
    - `/orders/history?current=true` - только активные заказы
    - `/orders/history?shop_id=7` - заказы конкретного магазина (только админ)
    - `/orders/history?courier_id=12` - заказы конкретного курьера (только админ)

    **Возвращаемые коды**:
    - `200`: список заказов успешно получен
    - `401`: пользователь не авторизован
    - `403`: попытка использовать запрещённый фильтр
    - `500`: внутренняя ошибка сервера
    """
    logger.info(
        f"Запрос истории заказов от пользователя {current_user}: "
        f"{page=}, {limit=}, {status=}, {shop_id=}, {courier_id=}, {current=}"
    )

    try:
        filters = OrderListFilters(
            page=page,
            limit=limit,
            status=status,
            shop_id=shop_id,
            courier_id=courier_id,
            current=current,
        )

        orders = await service.get_orders_list(
            db=db,
            user=current_user,
            filters=filters,
        )

        logger.info(
            f"Успешно получена история заказов для пользователя {current_user}: "
            f"всего={orders.total}, возвращено={len(orders.items)}"
        )
        return orders

    except OrderException as e:
        logger.warning(
            f"Ошибка доступа при получении истории заказов пользователем {current_user}: {e.detail}"
        )
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении истории заказов пользователем {current_user}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status_code.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось получить историю заказов",
        )
