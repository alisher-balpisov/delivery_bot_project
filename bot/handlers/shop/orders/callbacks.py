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
    page: int = 1
    status: str = "all"
    source: str | None = None


class OrdersListCallback(CallbackData, prefix="shop_orders"):
    """Пагинация списка заказов."""

    page: int = 1
    status: str = "all"  # active, completed, all


class OrderDetailCallback(CallbackData, prefix="shop_order_det"):
    """Переход к деталям заказа."""

    order_id: int
    from_page: int = 1
    from_status: str = "all"
    source: str | None = None


class OrderRefundCallback(CallbackData, prefix="shop_dispute"):
    """Callback data for dispute actions."""

    dispute_id: int
    action: str
    page: int = 1
    status: str = "all"


class DisputeReasonCallback(CallbackData, prefix="shop_dispute_reason"):
    """Callback data for dispute reason selection."""

    reason_id: int
    order_id: int
    page: int = 1
    status: str = "all"


class DisputesListCallback(CallbackData, prefix="shop_disps"):
    """Пагинация списка споров."""

    page: int = 1
    status: str | None = None
