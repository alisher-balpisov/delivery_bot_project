from fastapi import APIRouter, HTTPException, status

from backend.src.auth.dependencies import RequireAllRoles, RequireShop
from backend.src.common.enums import UserRole
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.orders import service
from backend.src.schemas.order import OrderCreate, OrderCreateRequest, OrderRead, OrderUpdate

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_new_order(
    order_in: OrderCreateRequest,
    current_user: RequireShop,
    db: DbSession,
):
    """
    Создание нового заказа. Доступно только магазинам.
    ID магазина берется из профиля аутентифицированного пользователя.

    Параметры:
    - **courier_id**: ID курьера (опционально, только для special заказов)
    - **order_type**: Тип заказа (regular или special)
    - **special_type**: Тип специального заказа (time, distance, custom, supply) - только для special
    - **price**: Цена доставки (устанавливается магазином)
    - **client_phone**: Телефон клиента (принимает любой формат)
    - **recipient_address**: Адрес получателя
    - **recipient_phone**: Телефон получателя (принимает любой формат)
    - **delivery_time**: Желаемое время доставки (опционально)
    - **description**: Описание/комментарии к заказу (опционально)
    """
    logger.info(f"Попытка создания заказа пользователем ID: {current_user.id}")

    if not current_user.shop:
        logger.error(
            f"Пользователь {current_user.id} с ролью SHOP не имеет связанного профиля магазина."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Профиль магазина не найден для вашего аккаунта",
        )

    # shop_id берется из аутентифицированного пользователя, а не из тела запроса
    order_data = OrderCreate(**order_in.model_dump(), shop_id=current_user.shop.id)

    try:
        result = await service.create_order(db=db, order_data=order_data)
        logger.info(
            f"Заказ успешно создан: id={result.id} для магазина shop_id={current_user.shop.id}"
        )
        return result
    except ValueError as e:
        logger.error(
            f"Ошибка валидации при создании заказа для пользователя {current_user.id}: {e!s}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ошибка валидации: {e!s}"
        )
    except Exception as e:
        logger.error(f"Создание заказа не удалось для пользователя {current_user.id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Не удалось создать заказ: {e!s}"
        )


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    # Проверка прав доступа
    logger.info(
        f"Проверка доступа к заказу {order_id} для пользователя {current_user.id}, роль {current_user.role}"
    )

    if current_user.role == UserRole.ADMIN:
        pass  # Админ видит все
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

    logger.info(f"Доступ разрешен для пользователя {current_user.id} к заказу {order_id}")
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
    Разные роли имеют разные права на изменение:
    - Админ: может изменять все
    - Магазин: может только отменить заказ
    - Курьер: может изменять статус и заметки
    """
    updated_order = await service.update_order(db, order_id, order_in, current_user)
    if not updated_order:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось обновить заказ",
        )
    return updated_order
