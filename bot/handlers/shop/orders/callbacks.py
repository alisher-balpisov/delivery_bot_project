"""Callback Data классы для заказов."""

from aiogram.filters.callback_data import CallbackData


class OrderTypeCallback(CallbackData, prefix="order_type"):
    """Выбор типа заказа."""

    type: str
    need_time: bool = False


class DeliveryTimeTypeCallback(CallbackData, prefix="set_del_time"):
    """Выбор типа времени доставки."""

    time_type: str


class CourierSelectionCallback(CallbackData, prefix="select_courier"):
    """Выбор курьера."""

    courier_id: int  # 0 для автовыбора, -1 для пагинации
    page: int = 1


class OrderActionCallback(CallbackData, prefix="shop_order_act"):
    """Действия с заказом."""

    order_id: int
    action: str


class OrdersListCallback(CallbackData, prefix="shop_orders"):
    """Пагинация списка заказов."""

    page: int = 1
    status: str = "all"  # active, completed, all


class OrderDetailCallback(CallbackData, prefix="shop_order_det"):
    """Переход к деталям заказа."""

    order_id: int
    from_page: int = 1
    from_status: str = "all"
