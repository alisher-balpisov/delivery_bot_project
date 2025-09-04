from datetime import timedelta

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.common.enums import OrderStatus, OrderType
from src.models.courier import Courier
from src.models.order import Order
from src.models.zone import Zone
from src.schemas.order import OrderCreate, OrderResponse


async def create_order(db: AsyncSession, order_data: OrderCreate) -> OrderResponse:
    """
    Создание нового заказа с расчетом цены.
    """
    # Получить зону для расчета цены
    zone = await db.get(Zone, order_data.zone_id)
    if not zone:
        raise ValueError("Указанная зона не найдена")

    # Расчет цены
    base_price = zone.base_price

    # Для special и rush_hour доплаты
    if order_data.order_type == OrderType.special:
        # Курьер видит цену, но базовая + доплата зоны
        pass  # уже есть zone_addon
    elif order_data.order_type == OrderType.rush_hour:
        # Вне 9-21
        if order_data.rush_hour_addon == 0:
            order_data.rush_hour_addon = 1000.0  # дефолт
    elif order_data.order_type == OrderType.long_distance:
        # Вне зоны, надбавка обязательна
        if order_data.zone_addon == 0:
            order_data.zone_addon = 500.0  # дефолт, но лучше указывать
    elif order_data.order_type == OrderType.important:
        # Специально для важных, без базовой, магазин указывает
        base_price = 0

    total_price = base_price + order_data.zone_addon + order_data.rush_hour_addon

    # Создать заказ
    order = Order(
        shop_id=order_data.shop_id,
        zone_id=order_data.zone_id,
        order_type=order_data.order_type,
        description=order_data.description or "",
        recipient_name=order_data.recipient_name or "",
        recipient_phone=order_data.recipient_phone,
        recipient_address=order_data.recipient_address,
        delivery_time=order_data.delivery_time,
        price=total_price,
        pickup_address=order_data.pickup_address,
        is_fragile=order_data.is_fragile,
        is_bulky=order_data.is_bulky,
        special_reason=order_data.special_reason,
        zone_addon=order_data.zone_addon,
        rush_hour_addon=order_data.rush_hour_addon,
    )

    db.add(order)
    await db.commit()
    await db.refresh(order)
    return OrderResponse.from_orm(order)


async def get_order_by_id(db: AsyncSession, order_id: int) -> OrderResponse | None:
    """
    Получение заказа по ID.
    """
    order = await db.get(Order, order_id)
    if order:
        return OrderResponse.from_orm(order)
    return None


async def get_orders_by_shop_id(db: AsyncSession, shop_id: int) -> list[OrderResponse]:
    """
    Получение заказов по ID магазина.
    """
    result = await db.execute(
        select(Order).where(Order.shop_id == shop_id).order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return [OrderResponse.from_orm(order) for order in orders]


async def get_available_couriers(db: AsyncSession) -> list[Courier]:
    """
    Получение доступных курьеров для назначения.
    """
    result = await db.execute(
        select(Courier).where(
            and_(Courier.is_active is True, Courier.current_orders < Courier.max_orders)
        )
    )
    return result.scalars().all()


async def assign_courier_manually(
    db: AsyncSession, order_id: int, courier_id: int
) -> OrderResponse:
    """
    Ручное назначение курьера на заказ (менеджерами или магазинами).
    """
    order = await db.get(Order, order_id)
    if not order:
        raise ValueError(f"Заказ {order_id} не найден")

    if order.status != OrderStatus.created:
        raise ValueError("Нельзя назначить курьера на заказ не в статусе 'created'")

    courier = await db.get(Courier, courier_id)
    if not courier or not courier.is_active:
        raise ValueError("Курьер недоступен")

    if courier.current_orders >= courier.max_orders:
        raise ValueError("У курьера нет свободных слотов")

    order.courier_id = courier_id
    order.status = OrderStatus.accepted
    order.accepted_at = func.now()

    courier.current_orders += 1

    # Для special типа, цена видна только после назначения
    # Для других типов цена фиксирована

    await db.commit()
    await db.refresh(order)
    return OrderResponse.from_orm(order)


async def assign_courier_automatically(db: AsyncSession, order_id: int) -> OrderResponse | None:
    """
    Автоматическое назначение курьера только для заказов типа 'special'.
    """
    order = await db.get(Order, order_id)
    if not order:
        raise ValueError(f"Заказ {order_id} не найден")

    if order.order_type != OrderType.special:
        raise ValueError("Автоматическое назначение доступно только для заказов типа 'special'")

    if order.status != OrderStatus.created:
        raise ValueError("Заказ уже назначен")

    available_couriers = await get_available_couriers(db)
    if not available_couriers:
        return None  # Нет доступных курьеров

    # Выбор курьера с минимальным количеством текущих заказов
    courier = min(available_couriers, key=lambda c: c.current_orders)

    order.courier_id = courier.id
    order.status = OrderStatus.accepted
    order.accepted_at = func.now()

    courier.current_orders += 1

    await db.commit()
    await db.refresh(order)
    return OrderResponse.from_orm(order)


async def update_order_status(
    db: AsyncSession, order_id: int, new_status: OrderStatus, courier_notes: str | None = None
) -> OrderResponse:
    """
    Обновление статуса заказа курьером или системой.
    """
    order = await db.get(Order, order_id)
    if not order:
        raise ValueError(f"Заказ {order_id} не найден")

    old_status = order.status
    order.status = new_status

    now = func.now()

    if new_status == OrderStatus.picking_up and old_status == OrderStatus.accepted:
        order.accepted_at = now  # уже установлено ранее

    elif new_status == OrderStatus.in_progress and old_status == OrderStatus.picking_up:
        pass  # в пути к получателю

    elif new_status == OrderStatus.delivered and old_status == OrderStatus.in_progress:
        order.delivered_at = now

    elif new_status == OrderStatus.completed and old_status == OrderStatus.delivered:
        order.confirmed_at = now

    elif new_status == OrderStatus.disputed:
        pass  # статус спор

    if courier_notes:
        order.courier_notes = courier_notes

    await db.commit()
    await db.refresh(order)
    return OrderResponse.from_orm(order)


async def confirm_order(db: AsyncSession, order_id: int) -> OrderResponse:
    """
    Подтверждение доставки заказа магазином вручную.
    """
    order = await db.get(Order, order_id)
    if not order:
        raise ValueError(f"Заказ {order_id} не найден")

    if order.status != OrderStatus.delivered:
        raise ValueError("Можно подтвердить только доставленный заказ")

    order.status = OrderStatus.completed
    order.confirmed_at = func.now()

    await db.commit()
    await db.refresh(order)
    return OrderResponse.from_orm(order)


async def auto_confirm_orders(db: AsyncSession) -> int:
    """
    Автоматическое подтверждение доставленных заказов спустя 12 часов.
    Возвращает количество подтвержденных заказов.
    """
    cutoff_time = func.now() - timedelta(hours=12)

    result = await db.execute(
        select(Order).where(
            and_(
                Order.status == OrderStatus.delivered,
                Order.delivered_at < cutoff_time,
                Order.confirmed_at.is_(None),
                Order.autoconfirmed_at.is_(None),
            )
        )
    )
    orders_to_confirm = result.scalars().all()

    count = 0
    for order in orders_to_confirm:
        order.status = OrderStatus.completed
        order.autoconfirmed_at = func.now()
        count += 1

    await db.commit()
    return count


async def rate_courier(
    db: AsyncSession, order_id: int, rating: int, feedback: str | None = None
) -> OrderResponse:
    """
    Оценка работы курьера по заказу (от 1 до 5).
    """
    if not 1 <= rating <= 5:
        raise ValueError("Оценка должна быть от 1 до 5")

    order = await db.get(Order, order_id)
    if not order:
        raise ValueError(f"Заказ {order_id} не найден")

    if order.status not in [OrderStatus.completed, OrderStatus.disputed]:
        raise ValueError("Можно оценить только выполненный заказ")

    if order.courier_rating is not None:
        raise ValueError("Заказ уже оценен")

    order.courier_rating = rating
    if feedback:
        order.courier_feedback = feedback

    await db.commit()
    await db.refresh(order)
    return OrderResponse.from_orm(order)
