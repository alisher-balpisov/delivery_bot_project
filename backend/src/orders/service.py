from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.src.common.constants import (
    COURIER_ALLOWED_FIELDS,
    FINAL_STATUSES,
    RESPONSE_SCHEMAS,
    RetrievePermissionCheck,
    UpdatePayload,
    UpdatePermissionCheck,
)
from backend.src.common.enums import OrderStatus, UserRole
from backend.src.core.logging import get_logger
from backend.src.models.courier import Courier
from backend.src.models.order import Order
from backend.src.models.shop import Shop
from backend.src.models.user import User
from backend.src.orders.exceptions import (
    OrderAccessForbiddenException,
    OrderNotFoundException,
    OrderUpdateForbiddenException,
)
from backend.src.orders.schemas import (
    OrderCreate,
    OrderCreateRequest,
    OrderResponse,
    OrderResponseForAdmin,
    OrderResponseForCourier,
    OrderResponseForShop,
    OrderUpdate,
)
from backend.src.users.exceptions import UserNotFoundException

logger = get_logger(__name__)


async def create_order(
    db: AsyncSession, order_in: OrderCreateRequest, shop_id: int
) -> OrderResponse:
    """Создаёт заказ для магазина и возвращает Pydantic-схему ответа."""

    order_data = OrderCreate(**order_in.model_dump(), shop_id=shop_id)
    await _ensure_courier_exists(db, order_data.courier_id)

    order = _build_order(order_data)
    db.add(order)
    await db.flush()
    await db.refresh(order)

    logger.info(f"Заказ {order} создан для магазина {order.shop}")
    return OrderResponse.model_validate(order)


def _build_order(order_data: OrderCreate) -> Order:
    """Создаёт ORM-объект заказа из входных данных."""

    return Order(
        shop_id=order_data.shop_id,
        courier_id=order_data.courier_id,
        status=OrderStatus.PENDING,
        order_type=order_data.order_type,
        special_type=order_data.special_type,
        price=order_data.price,
        client_phone=order_data.client_phone,
        recipient_address=order_data.recipient_address,
        recipient_phone=order_data.recipient_phone,
        delivery_time=order_data.delivery_time,
        description=order_data.description,
    )


async def _ensure_courier_exists(db: AsyncSession, courier_id: int | None) -> None:
    """Проверяет существование курьера в базе данных."""
    if courier_id is None:
        return

    courier = await db.get(Courier, courier_id)
    if courier is None:
        logger.error(f"Курьер {courier_id=} не найден при создании заказа")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Указанный курьер не найден: {courier_id=}",
        )


async def _ensure_update_permissions(
    user: User, order: Order, update_payload: UpdatePayload
) -> None:
    """Проверяет права пользователя на обновление заказа."""
    check = UPDATE_PERMISSION_CHECKS.get(user.role)
    if check is None:
        raise OrderUpdateForbiddenException()
    await check(user, order, update_payload)


async def _check_admin_update(_: User, order: Order, __: UpdatePayload) -> None:
    """Админ может обновлять любые заказы без ограничений."""
    logger.info(f"Админ обновляет заказ {order}")


async def _check_shop_update(user: User, order: Order, update_payload: UpdatePayload) -> None:
    """Проверяет права магазина на обновление заказа."""
    if not user.shop:
        logger.warning(f"Пользователь {user} без магазина обновляет заказ {order}")
        raise OrderUpdateForbiddenException()

    if order.shop_id != user.shop.id:
        logger.warning(f"Магазин {user.shop} попытался обновить чужой заказ {order}")
        raise OrderUpdateForbiddenException()

    # Магазин может изменить статус только на CANCELED. Другие поля изменять нельзя.
    update_keys = set(update_payload.keys())
    allowed_keys = {"status"}

    if not update_keys.issubset(allowed_keys):
        disallowed_fields = list(update_keys - allowed_keys)
        logger.warning(
            f"Магазин {user.shop} попытался обновить запрещённые поля: {disallowed_fields}"
        )
        raise OrderUpdateForbiddenException("Магазин может изменять только статус заказа.")

    status_value = update_payload.get("status")
    if status_value and status_value != OrderStatus.CANCELED:
        logger.warning(
            f"Магазин {user.shop} попытался изменить статус заказа {order} на {status_value}"
        )
        raise OrderUpdateForbiddenException("Магазин может только отменить заказ.")


async def _check_courier_update(user: User, order: Order, update_payload: UpdatePayload) -> None:
    """Проверяет права курьера на обновление заказа."""
    if not user.courier:
        logger.warning(f"Пользователь {user} без профиля курьера обновляет заказ {order}")
        raise OrderUpdateForbiddenException()

    if order.courier_id != user.courier.id:
        logger.warning(f"Курьер {user.courier} попытался обновить чужой заказ {order}")
        raise OrderUpdateForbiddenException()

    # Курьер может изменять только разрешённые поля
    if not set(update_payload).issubset(COURIER_ALLOWED_FIELDS):
        logger.warning(
            f"Курьер {user.courier} попытался обновить запрещённые поля {list(update_payload)}"
        )
        raise OrderUpdateForbiddenException()


def _apply_updates(order: Order, update_payload: UpdatePayload) -> None:
    """Применяет обновления к заказу."""
    for field, value in update_payload.items():
        setattr(order, field, value)


def _handle_status_side_effects(order: Order, previous_status: OrderStatus, user: User) -> None:
    """Обрабатывает побочные эффекты при изменении статуса заказа."""
    if order.status == previous_status:
        return

    if order.status == OrderStatus.COMPLETED:
        order.completed_at = datetime.now(UTC)

    logger.info(
        f"Статус заказа {order} изменён с {previous_status.value} на {order.status.value} пользователем {user}"
    )


def _ensure_order_is_modifiable(order: Order) -> None:
    """Проверяет, что заказ можно модифицировать (не в финальном статусе)."""
    if order.status in FINAL_STATUSES:
        logger.warning(f"Попытка изменить заказ {order} в финальном статусе {order.status.value}")
        raise OrderUpdateForbiddenException(
            f"Невозможно изменить заказ в статусе {order.status.value}"
        )


async def update_order(
    db: AsyncSession, order_id: int, update_data: OrderUpdate, current_user: User
) -> OrderResponse:
    """Обновляет заказ с учётом роли пользователя."""

    order = await db.get(Order, order_id)
    if order is None:
        raise OrderNotFoundException(order_id)

    update_payload = update_data.model_dump(exclude_unset=True)
    if not update_payload:
        return OrderResponse.model_validate(order)

    _ensure_order_is_modifiable(order)

    await _ensure_update_permissions(current_user, order, update_payload)

    new_courier_id = update_payload.get("courier_id")
    if new_courier_id is not None:
        await _ensure_courier_exists(db, new_courier_id)

    previous_status = order.status
    _apply_updates(order, update_payload)
    _handle_status_side_effects(order, previous_status, current_user)

    await db.flush()
    await db.refresh(order)

    return OrderResponse.model_validate(order)


async def _check_shop_retrieve_permissions(user: User, order: Order) -> None:
    """Проверяет права магазина на просмотр заказа."""
    if not user.shop:
        logger.warning(f"Пользователь {user} не имеет доступа к заказу {order}")
        raise OrderAccessForbiddenException()

    if order.shop_id != user.shop.id:
        logger.warning(f"Магазин {user.shop} не имеет доступа к заказу {order}")
        raise OrderAccessForbiddenException()


async def _check_courier_retrieve_permissions(user: User, order: Order) -> None:
    """Проверяет права курьера на просмотр заказа."""
    if not user.courier:
        logger.warning(f"Пользователь {user} без профиля курьера пытается получить заказ {order}")
        raise OrderAccessForbiddenException()

    if order.courier_id is None or order.courier_id != user.courier.id:
        logger.warning(f"Курьер {user.courier} не имеет доступа к заказу {order}")
        raise OrderAccessForbiddenException()


async def _check_admin_retrieve_permissions(user: User, order: Order) -> None:
    """Админ имеет доступ ко всем заказам."""
    logger.debug(f"Админ {user} запрашивает заказ {order}")


RETRIEVE_PERMISSION_CHECKS: dict[UserRole, RetrievePermissionCheck] = {
    UserRole.ADMIN: _check_admin_retrieve_permissions,
    UserRole.SHOP: _check_shop_retrieve_permissions,
    UserRole.COURIER: _check_courier_retrieve_permissions,
}


UPDATE_PERMISSION_CHECKS: dict[UserRole, UpdatePermissionCheck] = {
    UserRole.ADMIN: _check_admin_update,
    UserRole.SHOP: _check_shop_update,
    UserRole.COURIER: _check_courier_update,
}


async def get_order(
    db: AsyncSession, user_id: int, order_id: int
) -> OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier:
    """
    Возвращает информацию о заказе, адаптированную под роль пользователя.

    Оптимизирует запросы к БД, извлекает пользователя и заказ за один раз,
    использует стратегию на основе словаря для проверки прав и выбора схемы ответа.
    """
    user = await _fetch_user(db, user_id)
    order = await _fetch_order(db, order_id)

    permission_check = RETRIEVE_PERMISSION_CHECKS.get(user.role)
    response_schema = RESPONSE_SCHEMAS.get(user.role)

    if not permission_check or not response_schema:
        logger.warning(f"Пользователь {user} не имеет прав на просмотр заказов")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа",
        )

    await permission_check(user, order)
    return response_schema.model_validate(order)


async def _fetch_user(db: AsyncSession, user_id: int) -> User:
    """
    Загружает пользователя с предзагрузкой связанных данных.

    Предзагружает shop и courier, чтобы избежать N+1 запросов
    и проблем с lazy loading в async контексте.
    """
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            joinedload(User.shop),
            joinedload(User.courier),
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise UserNotFoundException(user_id)

    return user


async def _fetch_order(db: AsyncSession, order_id: int) -> Order:
    """
    Загружает заказ с предзагрузкой всех необходимых связанных данных.

    Использует joinedload для оптимизации запросов и предотвращения
    проблем с lazy loading в async контексте.
    """
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            joinedload(Order.shop).joinedload(Shop.user),
            joinedload(Order.courier).joinedload(Courier.user),
            joinedload(Order.history),
        )
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise OrderNotFoundException(order_id)

    return order
