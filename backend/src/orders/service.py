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
from backend.src.users.exceptions import UserNotFoundException

from .exceptions import (
    OrderAccessForbiddenException,
    OrderNotFoundException,
    OrderUpdateForbiddenException,
)
from .schemas import (
    OrderCreate,
    OrderCreateRequest,
    OrderResponse,
    OrderResponseForAdmin,
    OrderResponseForCourier,
    OrderResponseForShop,
    OrderUpdate,
)

logger = get_logger(__name__)


# ==================== СОЗДАНИЕ ЗАКАЗА ====================


async def create_order(db: AsyncSession, order_in: OrderCreateRequest, shop_id: int) -> Order:
    """
    Создаёт новый заказ для магазина.

    Args:
        db: Сессия базы данных
        order_in: Входные данные заказа от API
        shop_id: ID магазина, создающего заказ

    Returns:
        Созданный заказ в виде Pydantic-схемы

    Raises:
        HTTPException: Если указанный курьер не существует
    """
    order_data = _prepare_order_data(order_in, shop_id)
    await _validate_courier_for_order(db, order_data.courier_id)

    order = _create_order_entity(order_data)
    await _save_order_to_db(db, order)

    return order


def _prepare_order_data(order_in: OrderCreateRequest, shop_id: int) -> OrderCreate:
    """Преобразует входные данные API в внутреннюю схему с добавлением shop_id."""
    return OrderCreate(**order_in.model_dump(), shop_id=shop_id)


def _create_order_entity(order_data: OrderCreate) -> Order:
    """Создаёт ORM-объект заказа из схемы данных."""
    fields = (
        "shop_id",
        "courier_id",
        "order_type",
        "special_type",
        "price",
        "client_phone",
        "recipient_address",
        "recipient_phone",
        "delivery_time",
        "description",
    )

    return Order(
        status=OrderStatus.PENDING,
        **{f: getattr(order_data, f) for f in fields},
    )


async def _save_order_to_db(db: AsyncSession, order: Order) -> None:
    """Сохраняет заказ в базу данных и обновляет его ID."""
    db.add(order)
    await db.flush()
    await db.refresh(order)


async def _validate_courier_for_order(db: AsyncSession, courier_id: int | None) -> None:
    """
    Проверяет существование курьера в базе данных.

    Raises:
        HTTPException: Если курьер не найден
    """
    if courier_id is None:
        return

    courier = await db.get(Courier, courier_id)
    if courier is None:
        logger.error(f"Попытка создать заказ с несуществующим курьером {courier_id=}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Указанный курьер не найден: {courier_id=}",
        )


# ==================== ОБНОВЛЕНИЕ ЗАКАЗА ====================


async def update_order(
    db: AsyncSession, order_id: int, update_data: OrderUpdate, current_user: User
) -> Order:
    """
    Обновляет заказ с учётом роли и прав пользователя.

    Args:
        db: Сессия базы данных
        order_id: ID обновляемого заказа
        update_data: Данные для обновления
        current_user: Текущий пользователь, инициирующий обновление

    Returns:
        Обновлённый заказ в виде Pydantic-схемы

    Raises:
        OrderNotFoundException: Если заказ не найден
        OrderUpdateForbiddenException: Если у пользователя нет прав на обновление
    """
    order = await _fetch_order_for_update(db, order_id)
    update_payload = _extract_update_payload(update_data)

    if not update_payload:
        logger.debug(f"Пустое обновление заказа {order_id=}, возвращаем без изменений")
        return order

    _validate_order_can_be_modified(order)
    await _validate_update_permissions(current_user, order, update_payload)
    await _validate_courier_reassignment(db, update_payload)

    previous_status = order.status
    _apply_order_updates(order, update_payload)
    _process_status_change_effects(order, previous_status, current_user)

    await _commit_order_changes(db, order)
    return order


async def _fetch_order_for_update(db: AsyncSession, order_id: int) -> Order:
    """Загружает заказ для обновления или выбрасывает исключение, если не найден."""
    order = await db.get(Order, order_id)
    if order is None:
        raise OrderNotFoundException(order_id)
    return order


def _extract_update_payload(update_data: OrderUpdate) -> UpdatePayload:
    """Извлекает только установленные поля из схемы обновления."""
    return update_data.model_dump(exclude_unset=True)


def _validate_order_can_be_modified(order: Order) -> None:
    """
    Проверяет, что заказ находится в статусе, допускающем изменения.

    Raises:
        OrderUpdateForbiddenException: Если заказ в финальном статусе
    """
    if order.status in FINAL_STATUSES:
        logger.warning(f"Попытка изменить заказ {order} в финальном статусе {order.status.value}")
        raise OrderUpdateForbiddenException(
            f"Невозможно изменить заказ в статусе {order.status.value}"
        )


async def _validate_update_permissions(
    user: User, order: Order, update_payload: UpdatePayload
) -> None:
    """
    Проверяет права пользователя на обновление заказа.

    Raises:
        OrderUpdateForbiddenException: Если у пользователя нет прав
    """
    permission_check = UPDATE_PERMISSION_CHECKS.get(user.role)
    if permission_check is None:
        logger.warning(f"Неизвестная роль {user.role.value} при попытке обновить заказ {order}")
        raise OrderUpdateForbiddenException()

    await permission_check(user, order, update_payload)


async def _validate_courier_reassignment(db: AsyncSession, update_payload: UpdatePayload) -> None:
    """Проверяет существование нового курьера при переназначении."""
    new_courier_id = update_payload.get("courier_id")
    if new_courier_id is not None:
        await _validate_courier_for_order(db, new_courier_id)


def _apply_order_updates(order: Order, update_payload: UpdatePayload) -> None:
    """Применяет изменения к полям заказа."""
    for field, value in update_payload.items():
        setattr(order, field, value)


def _process_status_change_effects(order: Order, previous_status: OrderStatus, user: User) -> None:
    """
    Обрабатывает побочные эффекты при изменении статуса заказа.

    Например, устанавливает время завершения при переходе в статус COMPLETED.
    """
    if order.status == previous_status:
        return

    if order.status == OrderStatus.COMPLETED:
        order.completed_at = datetime.now(UTC)
        logger.info(f"Заказ {order} завершён пользователем {user}")

    logger.info(
        f"Статус заказа {order} изменён: {previous_status.value} -> {order.status.value} "
        f"(пользователь {user})"
    )


async def _commit_order_changes(db: AsyncSession, order: Order) -> None:
    """Сохраняет изменения заказа в базу данных."""
    await db.flush()
    await db.refresh(order)


# ==================== ПРОВЕРКА ПРАВ НА ОБНОВЛЕНИЕ ====================


async def _check_admin_update_permissions(_: User, order: Order, __: UpdatePayload) -> None:
    """Администратор может обновлять любые заказы без ограничений."""
    logger.debug(f"Администратор обновляет заказ {order.id}")


async def _check_shop_update_permissions(
    user: User, order: Order, update_payload: UpdatePayload
) -> None:
    """
    Проверяет права магазина на обновление заказа.

    Магазин может:
    - Изменять только свои заказы
    - Только отменять заказы (status -> CANCELED)

    Raises:
        OrderUpdateForbiddenException: Если магазин пытается изменить чужой заказ
            или недопустимые поля
    """
    _validate_shop_owns_order(user, order)
    _validate_shop_update_fields(user, update_payload)
    _validate_shop_status_change(user, order, update_payload)


def _validate_shop_owns_order(user: User, order: Order) -> None:
    """Проверяет, что заказ принадлежит магазину пользователя."""
    if not user.shop:
        logger.warning(f"Пользователь {user.id} без магазина пытается обновить заказ {order.id}")
        raise OrderUpdateForbiddenException()

    if order.shop_id != user.shop.id:
        logger.warning(
            f"Магазин {user.shop.id} попытался обновить чужой заказ {order.id} "
            f"(владелец: магазин {order.shop_id})"
        )
        raise OrderUpdateForbiddenException("Вы можете изменять только свои заказы")


def _validate_shop_update_fields(user: User, update_payload: UpdatePayload) -> None:
    """Проверяет, что магазин изменяет только разрешённые поля."""
    update_keys = set(update_payload.keys())
    allowed_keys = {"status"}

    if not update_keys.issubset(allowed_keys):
        disallowed_fields = list(update_keys - allowed_keys)
        logger.warning(
            f"Магазин {user.shop.id if user.shop else 'Unknown'} попытался изменить "
            f"запрещённые поля: {disallowed_fields}"
        )
        raise OrderUpdateForbiddenException("Магазин может изменять только статус заказа")


def _validate_shop_status_change(user: User, order: Order, update_payload: UpdatePayload) -> None:
    """Проверяет, что магазин меняет статус только на CANCELED."""
    status_value = update_payload.get("status")
    if status_value and status_value != OrderStatus.CANCELED:
        logger.warning(
            f"Магазин {user.shop.id if user.shop else 'Unknown'} попытался изменить статус "
            f"заказа {order.id} на {status_value} (разрешён только CANCELED)"
        )
        raise OrderUpdateForbiddenException("Магазин может только отменить заказ")


async def _check_courier_update_permissions(
    user: User, order: Order, update_payload: UpdatePayload
) -> None:
    """
    Проверяет права курьера на обновление заказа.

    Курьер может:
    - Изменять только назначенные ему заказы
    - Изменять только разрешённые поля (status, courier_notes, completion_notes)

    Raises:
        OrderUpdateForbiddenException: Если курьер пытается изменить чужой заказ
            или недопустимые поля
    """
    _validate_courier_profile_exists(user)
    _validate_courier_assigned_to_order(user, order)
    _validate_courier_update_fields(user, update_payload)


def _validate_courier_profile_exists(user: User) -> None:
    """Проверяет наличие профиля курьера у пользователя."""
    if not user.courier:
        logger.warning(f"Пользователь {user.id} без профиля курьера пытается обновить заказ")
        raise OrderUpdateForbiddenException("У вас нет профиля курьера")


def _validate_courier_assigned_to_order(user: User, order: Order) -> None:
    """Проверяет, что заказ назначен данному курьеру."""
    if order.courier_id != user.courier.id:
        logger.warning(
            f"Курьер {user.courier} попытался обновить чужой заказ {order} "
            f"(назначен курьеру {order.courier})"
        )
        raise OrderUpdateForbiddenException("Вы можете изменять только назначенные вам заказы")


def _validate_courier_update_fields(user: User, update_payload: UpdatePayload) -> None:
    """Проверяет, что курьер изменяет только разрешённые поля."""
    update_keys = set(update_payload.keys())

    if not update_keys.issubset(COURIER_ALLOWED_FIELDS):
        disallowed_fields = list(update_keys - COURIER_ALLOWED_FIELDS)
        logger.warning(
            f"Курьер {user.courier.id if user.courier else 'Unknown'} попытался изменить "
            f"запрещённые поля: {disallowed_fields}"
        )
        raise OrderUpdateForbiddenException(
            f"Курьер может изменять только поля: {', '.join(COURIER_ALLOWED_FIELDS)}"
        )


# ==================== ПОЛУЧЕНИЕ ЗАКАЗА ====================


async def get_order(
    db: AsyncSession, user_id: int, order_id: int
) -> OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier:
    """
    Возвращает информацию о заказе, адаптированную под роль пользователя.

    Args:
        db: Сессия базы данных
        user_id: ID пользователя, запрашивающего заказ
        order_id: ID запрашиваемого заказа

    Returns:
        Заказ в формате, соответствующем роли пользователя

    Raises:
        UserNotFoundException: Если пользователь не найден
        OrderNotFoundException: Если заказ не найден
        OrderAccessForbiddenException: Если у пользователя нет прав на просмотр
        HTTPException: Если роль пользователя не поддерживается
    """
    user = await _fetch_user_with_profiles(db, user_id)
    order = await _fetch_order_with_relations(db, order_id)

    await _validate_order_access_permissions(user, order)

    response_schema = _get_response_schema_for_role(user.role)
    return response_schema.model_validate(order)


async def _fetch_user_with_profiles(db: AsyncSession, user_id: int) -> User:
    """
    Загружает пользователя с предзагрузкой профилей магазина и курьера.

    Предотвращает проблемы с lazy loading в async контексте.

    Raises:
        UserNotFoundException: Если пользователь не найден
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
        logger.warning(f"Попытка получить заказ несуществующим пользователем {user_id}")
        raise UserNotFoundException(user_id)

    return user


async def _fetch_order_with_relations(db: AsyncSession, order_id: int) -> Order:
    """
    Загружает заказ с предзагрузкой всех связанных сущностей.

    Оптимизирует запросы к БД и предотвращает N+1 проблему.

    Raises:
        OrderNotFoundException: Если заказ не найден
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
        logger.warning(f"Попытка получить несуществующий заказ {order_id}")
        raise OrderNotFoundException(order_id)

    return order


async def _validate_order_access_permissions(user: User, order: Order) -> None:
    """
    Проверяет права пользователя на просмотр заказа.

    Raises:
        OrderAccessForbiddenException: Если у пользователя нет прав на просмотр
        HTTPException: Если роль пользователя не поддерживается
    """
    permission_check = RETRIEVE_PERMISSION_CHECKS.get(user.role)

    if not permission_check:
        logger.error(
            f"Неизвестная роль {user.role} при попытке получить заказ {order.id} "
            f"пользователем {user.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа",
        )

    await permission_check(user, order)


def _get_response_schema_for_role(
    role: UserRole,
) -> type[OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier]:
    """
    Возвращает схему ответа, соответствующую роли пользователя.

    Raises:
        HTTPException: Если для роли нет соответствующей схемы
    """
    response_schema = RESPONSE_SCHEMAS.get(role)

    if not response_schema:
        logger.error(f"Нет схемы ответа для роли {role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа",
        )

    return response_schema


# ==================== ПРОВЕРКА ПРАВ НА ПРОСМОТР ====================


async def _check_admin_retrieve_permissions(user: User, order: Order) -> None:
    """Администратор имеет доступ ко всем заказам."""
    logger.debug(f"Администратор {user.id} запрашивает заказ {order.id}")


async def _check_shop_retrieve_permissions(user: User, order: Order) -> None:
    """
    Проверяет права магазина на просмотр заказа.

    Магазин может просматривать только свои заказы.

    Raises:
        OrderAccessForbiddenException: Если заказ не принадлежит магазину
    """
    if not user.shop:
        logger.warning(f"Пользователь {user.id} без магазина пытается получить заказ {order.id}")
        raise OrderAccessForbiddenException()

    if order.shop_id != user.shop.id:
        logger.warning(
            f"Магазин {user.shop.id} попытался получить чужой заказ {order.id} "
            f"(владелец: магазин {order.shop_id})"
        )
        raise OrderAccessForbiddenException()


async def _check_courier_retrieve_permissions(user: User, order: Order) -> None:
    """
    Проверяет права курьера на просмотр заказа.

    Курьер может просматривать только назначенные ему заказы.

    Raises:
        OrderAccessForbiddenException: Если заказ не назначен курьеру
    """
    if not user.courier:
        logger.warning(
            f"Пользователь {user.id} без профиля курьера пытается получить заказ {order.id}"
        )
        raise OrderAccessForbiddenException()

    if order.courier_id is None or order.courier_id != user.courier.id:
        logger.warning(
            f"Курьер {user.courier.id} попытался получить не назначенный ему заказ {order.id} "
            f"(назначен курьеру {order.courier_id})"
        )
        raise OrderAccessForbiddenException()


# ==================== МАППИНГИ ПРОВЕРОК ПРАВ ====================


RETRIEVE_PERMISSION_CHECKS: dict[UserRole, RetrievePermissionCheck] = {
    UserRole.ADMIN: _check_admin_retrieve_permissions,
    UserRole.SHOP: _check_shop_retrieve_permissions,
    UserRole.COURIER: _check_courier_retrieve_permissions,
}


UPDATE_PERMISSION_CHECKS: dict[UserRole, UpdatePermissionCheck] = {
    UserRole.ADMIN: _check_admin_update_permissions,
    UserRole.SHOP: _check_shop_update_permissions,
    UserRole.COURIER: _check_courier_update_permissions,
}
