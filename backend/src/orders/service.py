from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.src.common.constants import (
    COURIER_ALLOWED_FIELDS,
    FINAL_STATUSES,
    RESPONSE_SCHEMAS,
    PaginatedResponse,
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
    OrderListFilters,
    OrderListItemForAdmin,
    OrderListItemForCourier,
    OrderListItemForShop,
    OrderUpdate,
)

logger = get_logger(__name__)


# ==================== СОЗДАНИЕ ЗАКАЗА ====================


async def create_order(db: AsyncSession, order_in: OrderCreateRequest, shop_id: int) -> Order:
    """
    Создаёт новый заказ для магазина.

    Args:
        db: Сессия базы данных
        order_in: Данные заказа от API
        shop_id: ID магазина-создателя

    Returns:
        Созданный заказ

    Raises:
        HTTPException: Если курьер не существует (для special заказов)
    """
    # Преобразуем внешнюю схему во внутреннюю
    order_data = OrderCreate(**order_in.model_dump(), shop_id=shop_id)

    # Валидируем курьера для special заказов
    if order_data.courier_id:
        await _validate_courier_exists(db, order_data.courier_id)

    # Создаём ORM-объект
    order = _build_order_entity(order_data)

    # Сохраняем в БД
    db.add(order)
    await db.flush()
    await db.refresh(order)

    logger.info(
        f"Создан заказ {order}: shop_id={shop_id}, "
        f"type={order.order_type.value}, courier_id={order.courier_id}"
    )

    return order


def _build_order_entity(order_data: OrderCreate) -> Order:
    """Создаёт ORM-модель заказа из схемы данных."""
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


async def _validate_courier_exists(db: AsyncSession, courier_id: int) -> None:
    """
    Проверяет существование курьера в БД.

    Raises:
        HTTPException: Если курьер не найден
    """
    courier = await db.get(Courier, courier_id)
    if not courier:
        logger.error(f"Попытка создать заказ с несуществующим courier_id={courier_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Курьер с ID {courier_id} не найден",
        )


# ==================== ОБНОВЛЕНИЕ ЗАКАЗА ====================


async def update_order(
    db: AsyncSession, order_id: int, update_data: OrderUpdate, current_user: User
) -> Order:
    """
    Обновляет заказ с учётом ролевых прав.

    Args:
        db: Сессия базы данных
        order_id: ID заказа
        update_data: Данные для обновления
        current_user: Пользователь, инициирующий обновление

    Returns:
        Обновлённый заказ

    Raises:
        OrderNotFoundException: Заказ не найден
        OrderUpdateForbiddenException: Нет прав на обновление
    """
    order = await _fetch_order_or_404(db, order_id)

    # Извлекаем только установленные поля
    update_payload = update_data.model_dump(exclude_unset=True)

    if not update_payload:
        logger.debug(f"Пустое обновление заказа {order_id}, возвращаем без изменений")
        return order

    # Проверяем возможность изменения
    _ensure_order_not_finalized(order)

    # Проверяем права доступа
    await _verify_update_permissions(current_user, order, update_payload)

    # Валидируем нового курьера при переназначении
    if "courier_id" in update_payload:
        await _validate_courier_exists(db, update_payload["courier_id"])

    # Применяем изменения
    previous_status = order.status
    _apply_updates_to_order(order, update_payload)

    # Обрабатываем побочные эффекты
    _handle_status_change_side_effects(order, previous_status, current_user)

    # Сохраняем
    await db.flush()
    await db.refresh(order)

    logger.info(
        f"Заказ {order_id} обновлён пользователем {current_user.id} "
        f"(роль: {current_user.role.value})"
    )

    return order


async def _fetch_order_or_404(db: AsyncSession, order_id: int) -> Order:
    """Загружает заказ или выбрасывает 404."""
    order = await db.get(Order, order_id)
    if not order:
        raise OrderNotFoundException(order_id)
    return order


def _ensure_order_not_finalized(order: Order) -> None:
    """
    Проверяет, что заказ не в финальном статусе.

    Raises:
        OrderUpdateForbiddenException: Если заказ завершён/отменён
    """
    if order.status in FINAL_STATUSES:
        logger.warning(
            f"Попытка изменить заказ {order.id} в финальном статусе {order.status.value}"
        )
        raise OrderUpdateForbiddenException(
            f"Невозможно изменить заказ в статусе {order.status.value}"
        )


async def _verify_update_permissions(
    user: User, order: Order, update_payload: dict[str, Any]
) -> None:
    """
    Проверяет права пользователя на обновление.

    Вызывает соответствующую функцию проверки в зависимости от роли.

    Raises:
        OrderUpdateForbiddenException: Если нет прав
    """
    permission_checks = {
        UserRole.ADMIN: _verify_admin_can_update,
        UserRole.SHOP: _verify_shop_can_update,
        UserRole.COURIER: _verify_courier_can_update,
    }

    check_func = permission_checks.get(user.role)

    if not check_func:
        logger.error(f"Неизвестная роль {user.role.value} при обновлении заказа")
        raise OrderUpdateForbiddenException("Недостаточно прав")

    await check_func(user, order, update_payload)


async def _verify_admin_can_update(
    user: User, order: Order, update_payload: dict[str, Any]
) -> None:
    """Администратор может обновлять любые заказы."""
    logger.debug(f"Администратор {user.id} обновляет заказ {order.id}")


async def _verify_shop_can_update(user: User, order: Order, update_payload: dict[str, Any]) -> None:
    """
    Проверяет права магазина на обновление.

    Магазин может:
    - Изменять только свои заказы
    - Только отменять их (status -> CANCELED)
    """
    if not user.shop:
        raise OrderUpdateForbiddenException("У вас нет профиля магазина")

    # Проверяем владение заказом
    if order.shop_id != user.shop.id:
        logger.warning(f"Магазин {user.shop.id} попытался обновить чужой заказ {order.id}")
        raise OrderUpdateForbiddenException("Вы можете изменять только свои заказы")

    # Проверяем разрешённые поля
    allowed_fields = {"status"}
    if not set(update_payload.keys()).issubset(allowed_fields):
        raise OrderUpdateForbiddenException("Магазин может изменять только статус заказа")

    # Проверяем допустимый статус
    if "status" in update_payload and update_payload["status"] != OrderStatus.CANCELED:
        raise OrderUpdateForbiddenException("Магазин может только отменить заказ")


async def _verify_courier_can_update(
    user: User, order: Order, update_payload: dict[str, Any]
) -> None:
    """
    Проверяет права курьера на обновление.

    Курьер может:
    - Изменять только назначенные ему заказы
    - Только разрешённые поля (status, courier_notes, completion_notes)
    """
    if not user.courier:
        raise OrderUpdateForbiddenException("У вас нет профиля курьера")

    # Проверяем назначение
    if order.courier_id != user.courier.id:
        logger.warning(f"Курьер {user.courier.id} попытался обновить не свой заказ {order.id}")
        raise OrderUpdateForbiddenException("Вы можете изменять только назначенные вам заказы")

    # Проверяем разрешённые поля
    if not set(update_payload.keys()).issubset(COURIER_ALLOWED_FIELDS):
        forbidden = set(update_payload.keys()) - COURIER_ALLOWED_FIELDS
        logger.warning(f"Курьер {user.courier.id} попытался изменить поля: {forbidden}")
        raise OrderUpdateForbiddenException(
            f"Курьер может изменять только: {', '.join(COURIER_ALLOWED_FIELDS)}"
        )


def _apply_updates_to_order(order: Order, update_payload: dict[str, Any]) -> None:
    """Применяет изменения к полям заказа."""
    for field, value in update_payload.items():
        setattr(order, field, value)


def _handle_status_change_side_effects(
    order: Order, previous_status: OrderStatus, user: User
) -> None:
    """
    Обрабатывает побочные эффекты при смене статуса.

    Например, устанавливает completed_at при завершении.
    """
    if order.status == previous_status:
        return

    if order.status == OrderStatus.COMPLETED:
        order.completed_at = datetime.now(UTC)
        logger.info(f"Заказ {order.id} завершён пользователем {user.id}")

    logger.info(
        f"Статус заказа {order.id} изменён: {previous_status.value} -> {order.status.value}"
    )


# ==================== ПОЛУЧЕНИЕ ЗАКАЗА ====================


async def get_order(db: AsyncSession, user_id: int, order_id: int):
    """
    Возвращает детальную информацию о заказе.

    Формат ответа адаптирован под роль пользователя.

    Args:
        db: Сессия БД
        user_id: ID пользователя
        order_id: ID заказа

    Returns:
        OrderResponseForAdmin | OrderResponseForShop | OrderResponseForCourier

    Raises:
        UserNotFoundException: Пользователь не найден
        OrderNotFoundException: Заказ не найден
        OrderAccessForbiddenException: Нет прав на просмотр
    """
    user = await _fetch_user_with_relations(db, user_id)
    order = await _fetch_order_with_relations(db, order_id)

    # Проверяем права доступа
    await _verify_retrieve_permissions(user, order)

    # Возвращаем в нужном формате
    response_schema = RESPONSE_SCHEMAS.get(user.role)

    if not response_schema:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав доступа"
        )

    return response_schema.model_validate(order)


async def _fetch_user_with_relations(db: AsyncSession, user_id: int) -> User:
    """
    Загружает пользователя с профилями shop/courier.

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

    if not user:
        raise UserNotFoundException(user_id)

    return user


async def _fetch_order_with_relations(db: AsyncSession, order_id: int) -> Order:
    """
    Загружает заказ со всеми связанными данными.

    Оптимизирует запросы к БД, избегая N+1 проблемы.

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

    if not order:
        raise OrderNotFoundException(order_id)

    return order


async def _verify_retrieve_permissions(user: User, order: Order) -> None:
    """
    Проверяет права на просмотр заказа.

    Raises:
        OrderAccessForbiddenException: Если нет прав
    """
    permission_checks = {
        UserRole.ADMIN: _verify_admin_can_retrieve,
        UserRole.SHOP: _verify_shop_can_retrieve,
        UserRole.COURIER: _verify_courier_can_retrieve,
    }

    check_func = permission_checks.get(user.role)

    if not check_func:
        raise OrderAccessForbiddenException("Недостаточно прав")

    await check_func(user, order)


async def _verify_admin_can_retrieve(user: User, order: Order) -> None:
    """Администратор имеет доступ ко всем заказам."""
    logger.debug(f"Администратор {user.id} запрашивает заказ {order.id}")


async def _verify_shop_can_retrieve(user: User, order: Order) -> None:
    """Магазин может просматривать только свои заказы."""
    if not user.shop or order.shop_id != user.shop.id:
        logger.warning(
            f"Магазин {user.shop.id if user.shop else 'N/A'} попытался получить чужой заказ {order.id}"
        )
        raise OrderAccessForbiddenException()


async def _verify_courier_can_retrieve(user: User, order: Order) -> None:
    """Курьер может просматривать только назначенные ему заказы."""
    if not user.courier or order.courier_id != user.courier.id:
        logger.warning(
            f"Курьер {user.courier.id if user.courier else 'N/A'} попытался получить чужой заказ {order.id}"
        )
        raise OrderAccessForbiddenException()


# ==================== СПИСОК ЗАКАЗОВ ====================


async def get_orders_list(
    db: AsyncSession,
    user: User,
    filters: OrderListFilters,
) -> PaginatedResponse:
    """
    Возвращает пагинированный список заказов с фильтрами.

    Список адаптирован под роль пользователя.

    Args:
        db: Сессия БД
        user: Текущий пользователь
        filters: Параметры фильтрации и пагинации

    Returns:
        PaginatedResponse с заказами

    Raises:
        HTTPException: При попытке использовать запрещённые фильтры
    """
    # Валидируем фильтры для роли
    _validate_filters_for_role(user, filters)

    # Строим запрос
    stmt = _build_orders_query(user, filters)

    # Считаем общее количество
    total = await _count_orders(db, stmt)

    # Применяем пагинацию
    stmt = stmt.offset((filters.page - 1) * filters.limit).limit(filters.limit)

    # Получаем заказы
    result = await db.execute(stmt)
    orders = result.scalars().all()

    # Преобразуем в схемы
    response_schema = _get_list_item_schema(user.role)
    items = [response_schema.model_validate(order) for order in orders]

    logger.info(
        f"Получен список заказов для {user.role.value} {user.id}: "
        f"total={total}, page={filters.page}, items={len(items)}"
    )

    return PaginatedResponse(total=total, items=items)


def _validate_filters_for_role(user: User, filters: OrderListFilters) -> None:
    """
    Проверяет допустимость фильтров для роли.

    Raises:
        HTTPException: Если используется запрещённый фильтр
    """
    if user.role == UserRole.ADMIN:
        return

    if filters.shop_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Фильтр shop_id доступен только администраторам",
        )

    if filters.courier_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Фильтр courier_id доступен только администраторам",
        )


def _build_orders_query(user: User, filters: OrderListFilters):
    """Строит SQL-запрос с учётом роли и фильтров."""
    stmt = (
        select(Order)
        .options(
            joinedload(Order.shop).joinedload(Shop.user),
            joinedload(Order.courier).joinedload(Courier.user),
        )
        .order_by(Order.created_at.desc())
    )

    # Применяем фильтры в зависимости от роли
    if user.role == UserRole.SHOP:
        stmt = _apply_shop_filters(stmt, user, filters)
    elif user.role == UserRole.COURIER:
        stmt = _apply_courier_filters(stmt, user, filters)
    elif user.role == UserRole.ADMIN:
        stmt = _apply_admin_filters(stmt, filters)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    return stmt


def _apply_shop_filters(stmt, user: User, filters: OrderListFilters):
    """Применяет фильтры для магазина."""
    if not user.shop:
        raise OrderAccessForbiddenException("У вас нет профиля магазина")

    # Магазин видит только свои заказы
    stmt = stmt.where(Order.shop_id == user.shop.id)

    # Фильтр по статусу
    if filters.status:
        stmt = stmt.where(Order.status == filters.status)

    # Фильтр по текущим/завершённым
    if filters.current is True:
        stmt = stmt.where(Order.status.not_in(FINAL_STATUSES))
    elif filters.current is False:
        stmt = stmt.where(Order.status.in_(FINAL_STATUSES))

    return stmt


def _apply_courier_filters(stmt, user: User, filters: OrderListFilters):
    """Применяет фильтры для курьера."""
    if not user.courier:
        raise OrderAccessForbiddenException("У вас нет профиля курьера")

    # Курьер видит только свои заказы
    stmt = stmt.where(Order.courier_id == user.courier.id)

    # Фильтр по статусу
    if filters.status:
        stmt = stmt.where(Order.status == filters.status)

    # Фильтр по текущим/завершённым
    if filters.current is True:
        stmt = stmt.where(Order.status.not_in(FINAL_STATUSES))
    elif filters.current is False:
        stmt = stmt.where(Order.status.in_(FINAL_STATUSES))

    return stmt


def _apply_admin_filters(stmt, filters: OrderListFilters):
    """Применяет фильтры для администратора."""
    if filters.shop_id:
        stmt = stmt.where(Order.shop_id == filters.shop_id)

    if filters.courier_id:
        stmt = stmt.where(Order.courier_id == filters.courier_id)

    if filters.status:
        stmt = stmt.where(Order.status == filters.status)

    if filters.current is True:
        stmt = stmt.where(Order.status.not_in(FINAL_STATUSES))
    elif filters.current is False:
        stmt = stmt.where(Order.status.in_(FINAL_STATUSES))

    return stmt


async def _count_orders(db: AsyncSession, stmt) -> int:
    """Подсчитывает общее количество заказов."""
    count_stmt = select(func.count()).select_from(stmt.subquery())
    result = await db.execute(count_stmt)
    return result.scalar_one()


def _get_list_item_schema(role: UserRole):
    """Возвращает схему элемента списка для роли."""
    schemas = {
        UserRole.ADMIN: OrderListItemForAdmin,
        UserRole.SHOP: OrderListItemForShop,
        UserRole.COURIER: OrderListItemForCourier,
    }

    schema = schemas.get(role)

    if not schema:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    return schema


# ==================== ЗАВЕРШЕНИЕ ЗАКАЗА ====================


async def complete_order(
    db: AsyncSession, order_id: int, photo_report_id: str, current_user: User
) -> Order:
    """
    Завершает заказ с фото-отчётом.

    Args:
        db: Сессия БД
        order_id: ID заказа
        photo_report_id: ID фото в Telegram
        current_user: Курьер, завершающий заказ

    Returns:
        Завершённый заказ

    Raises:
        OrderNotFoundException: Заказ не найден
        OrderUpdateForbiddenException: Нет прав или неверный статус
    """
    order = await _fetch_order_or_404(db, order_id)

    # Проверяем, что это курьер
    if current_user.role != UserRole.COURIER:
        raise OrderUpdateForbiddenException("Только курьер может завершить заказ")

    # Проверяем назначение
    if not current_user.courier or order.courier_id != current_user.courier.id:
        raise OrderUpdateForbiddenException("Вы можете завершать только назначенные вам заказы")

    # Проверяем статус
    allowed_statuses = {OrderStatus.DELIVERING, OrderStatus.SEMI_COMPLETED}
    if order.status not in allowed_statuses:
        raise OrderUpdateForbiddenException(
            f"Невозможно завершить заказ в статусе {order.status.value}. "
            f"Заказ должен быть в процессе доставки"
        )

    # Завершаем заказ
    order.status = OrderStatus.COMPLETED
    order.photo_report_id = photo_report_id
    order.completed_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(order)

    logger.info(f"Заказ {order_id} завершён курьером {current_user.courier.id}")

    return order
