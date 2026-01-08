from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status

from backend.src.auth.dependencies import RequireAllRoles, RequireCourier, RequireShop
from backend.src.common.constants import PaginatedResponse
from backend.src.common.dependencies import PaginationParams
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


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Создать заказ",
    tags=["Orders - Shop"],
)
async def create_order(
    order_in: OrderCreateRequest,
    current_user: RequireShop,
    db: DbSession,
):
    """
    Создаёт новый заказ от имени магазина.

    ## Права доступа
    - Доступно только магазинам

    ## Типы заказов
    - **regular**: обычный заказ, курьер назначается автоматически
    - **special**: специальный заказ, требуется указать courier_id

    ## Коды ответа
    - **201**: заказ успешно создан
    - **400**: некорректные данные или курьер не найден
    - **401**: пользователь не авторизован
    - **403**: недостаточно прав (не магазин)
    """
    logger.info(f"Создание заказа: {current_user.shop}, order_type={order_in.order_type.value}")

    try:
        order = await service.create_order(
            db=db,
            order_in=order_in,
            shop_id=current_user.shop.id,  # type: ignore
        )

        logger.info(f"✓ Заказ {order} создан магазином {current_user.shop}")
        return order

    except ValueError as e:
        logger.warning(f"Ошибка валидации при создании заказа: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании заказа: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера",
        )


@router.patch(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Обновить заказ",
    tags=["Orders - All Roles"],
)
async def update_order(
    order_id: int,
    order_in: OrderUpdate,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Обновляет существующий заказ.

    ## Права по ролям
    - **Администратор**: может изменять любые поля любых заказов
    - **Магазин**: может только отменить свой заказ (status → CANCELED)
    - **Курьер**: может изменять status, courier_notes, completion_notes своих заказов

    ## Ограничения
    - Нельзя изменять заказы в финальных статусах (COMPLETED, CANCELED)

    ## Коды ответа
    - **200**: заказ успешно обновлён
    - **400**: некорректные данные
    - **401**: пользователь не авторизован
    - **403**: недостаточно прав
    - **404**: заказ не найден
    """
    update_fields = list(order_in.model_dump(exclude_unset=True).keys())
    logger.info(
        f"Обновление заказа {order_id=}: пользователем {current_user}, fields={update_fields}"
    )

    try:
        updated_order = await service.update_order(
            db=db,
            order_id=order_id,
            update_data=order_in,
            current_user=current_user,
        )

        logger.info(f"✓ Заказ {order_id=} обновлён пользователем {current_user}")
        return updated_order

    except OrderException:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обновлении заказа {order_id=}: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера",
        )


@router.put(
    "/{order_id}/complete",
    response_model=OrderResponse,
    summary="Завершить заказ",
    tags=["Orders - Courier"],
)
async def complete_order(
    order_id: int,
    request: OrderCompleteRequest,
    current_user: RequireCourier,
    db: DbSession,
):
    """
    Завершает заказ с загрузкой фото-отчёта.

    ## Права доступа
    - Доступно только курьерам, назначенным на заказ

    ## Требования
    - Заказ должен быть в статусе **DELIVERING** или **AWAITING_CONFIRMATION**
    - Необходимо предоставить photo_report_id (ID фото в Telegram)

    ## Результат
    - Статус меняется на **COMPLETED**
    - Сохраняется photo_report_id
    - Устанавливается completed_at

    ## Коды ответа
    - **200**: заказ успешно завершён
    - **400**: некорректные данные
    - **401**: не авторизован
    - **403**: не назначен на заказ или неверный статус
    - **404**: заказ не найден
    """
    logger.info(
        f"Завершение заказа {order_id=}: курьером {current_user.courier}, "
        f"photo_id={request.photo_report_id}"
    )

    try:
        completed_order = await service.complete_order(
            db=db,
            order_id=order_id,
            photo_report_id=request.photo_report_id,
            current_user=current_user,
        )

        logger.info(f"✓ Заказ {order_id=} завершён курьером {current_user.courier}")
        return completed_order

    except OrderException:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при завершении заказа {order_id=}: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера",
        )


@router.get(
    "/history",
    response_model=PaginatedResponse[
        OrderListItemForAdmin | OrderListItemForShop | OrderListItemForCourier
    ],
    summary="Получить историю заказов",
    tags=["Orders - All Roles"],
)
async def get_orders_history(
    current_user: RequireAllRoles,
    db: DbSession,
    pagination: PaginationParams,
    status: Annotated[OrderStatus | None, Query(description="Фильтр по статусу")] = None,
    shop_id: Annotated[int | None, Query(description="Фильтр по магазину (только админ)")] = None,
    courier_id: Annotated[int | None, Query(description="Фильтр по курьеру (только админ)")] = None,
    current: Annotated[bool | None, Query(description="true=активные, false=завершённые")] = None,
):
    """
    Возвращает историю заказов с пагинацией и фильтрами.

    ## Права по ролям

    ### Магазин
    - Видит только свои заказы
    - Доступные фильтры: `status`, `current`

    ### Курьер
    - Видит только назначенные ему заказы
    - Доступные фильтры: `status`, `current`

    ### Администратор
    - Видит все заказы
    - Доступные фильтры: `status`, `shop_id`, `courier_id`, `current`

    ## Параметры
    - **page**: номер страницы (по умолчанию 1)
    - **limit**: элементов на странице (1-100, по умолчанию 20)
    - **status**: фильтр по статусу
    - **shop_id**: фильтр по магазину (только админ)
    - **courier_id**: фильтр по курьеру (только админ)
    - **current**: true - активные, false - завершённые

    ## Примеры
    - `/orders/history` - первая страница
    - `/orders/history?page=2&limit=50` - вторая страница по 50
    - `/orders/history?status=completed` - только завершённые
    - `/orders/history?current=true` - только активные
    - `/orders/history?shop_id=7` - по магазину (админ)

    ## Коды ответа
    - **200**: список успешно получен
    - **401**: не авторизован
    - **403**: попытка использовать запрещённый фильтр
    """
    page, limit = pagination
    logger.info(
        f"Запрос истории заказов: пользователем {current_user},"
        f"{page=}, {limit=}, {status=}, {shop_id=}, "
        f"{courier_id=}, {current=}"
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

        result = await service.get_orders_list(
            db=db,
            user=current_user,
            filters=filters,
        )

        logger.info(
            f"✓ История заказов получена: пользователем {current_user}, "
            f"total={result.total}, returned={len(result.items)}"
        )
        return result

    except OrderException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении истории заказов: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось получить историю заказов",
        )


@router.get(
    "/{order_id}",
    response_model=OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier,
    summary="Получить заказ",
    tags=["Orders - All Roles"],
)
async def get_order(
    order_id: int,
    current_user: RequireAllRoles,
    db: DbSession,
):
    """
    Возвращает детальную информацию о заказе.

    ## Права доступа
    - **Администратор**: доступ ко всем заказам с полной информацией
    - **Магазин**: доступ только к своим заказам
    - **Курьер**: доступ только к назначенным ему заказам

    ## Форматы ответа
    Формат зависит от роли:
    - Администратор получает полную информацию
    - Магазин видит данные курьера
    - Курьер видит данные магазина

    ## Коды ответа
    - **200**: заказ успешно получен
    - **401**: не авторизован
    - **403**: нет прав на просмотр
    - **404**: заказ не найден
    """
    logger.info(f"Запрос заказа {order_id=}: пользователем {current_user}")

    try:
        order = await service.get_order(
            db=db,
            user_id=current_user.id,
            order_id=order_id,
        )

        logger.info(f"✓ Заказ {order_id=} получен пользователем {current_user}")
        return order

    except OrderException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении заказа {order_id=}: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось получить заказ",
        )
