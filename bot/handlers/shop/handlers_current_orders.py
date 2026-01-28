# handlers_current_orders.py — Хендлеры просмотра заказов для магазина
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.messages import ShopOrdersMessages as SOM
from bot.keyboards.orders import get_order_details_keyboard, get_orders_list_keyboard
from bot.redis_storage import UserDataStorage
from bot.utils.order_formatters import format_order_details
from bot.utils.token_manager import TokenManager

logger = get_logger(__name__)

router = Router(name="shop_current_orders_handlers")
router.message.filter(RoleFilter(UserRole.SHOP))
router.callback_query.filter(RoleFilter(UserRole.SHOP))

ORDERS_PER_PAGE = 5


class ShopOrdersListCallback(CallbackData, prefix="shop_orders"):
    page: int = 1
    status: str = "all"  # active, completed, all


class ShopOrderDetailCallback(CallbackData, prefix="shop_order_det"):
    order_id: int
    from_page: int = 1
    from_status: str = "all"


class ShopOrderActionCallback(CallbackData, prefix="shop_order_act"):
    order_id: int
    action: str  # cancel, etc.


async def execute_api_call(
    token_manager: TokenManager, user_id: int, func: Callable[..., Any], **kwargs
) -> Any:
    """
    Выполняет API-запрос с автоматическим обновлением токена при 401 ошибке.
    """
    token = await token_manager.get_token(user_id)
    result = await func(token=token, **kwargs)

    if result.status_code == 401:
        token = await token_manager.get_token(user_id, force_refresh=True)
        if token:
            result = await func(token=token, **kwargs)

    return result


@router.callback_query(F.data == "show_current_orders")
@router.callback_query(ShopOrdersListCallback.filter())
async def show_current_orders_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: ShopOrdersListCallback | None = None,
):
    """Отображает список заказов магазина с пагинацией и фильтрацией."""
    # Если запущен через "show_current_orders" (меню), создаем дефолтный объект
    if callback_data is None:
        callback_data = ShopOrdersListCallback(page=1, status="all")

    page = callback_data.page
    filter_status = callback_data.status

    token_manager = TokenManager(auth_client, user_storage)

    # Логика маппинга фильтра в параметр API
    current = None
    if filter_status == "active":
        current = True
    elif filter_status == "completed":
        current = False

    # Выполняем запрос через безопасную обертку
    result = await execute_api_call(
        token_manager=token_manager,
        user_id=callback.from_user.id,
        func=orders_client.get_orders_history,
        page=page,
        limit=ORDERS_PER_PAGE,
        current=current,
    )

    if not result.success:
        # Пытаемся достать детальное описание ошибки, если есть
        error_msg = result.data.get("detail", "Ошибка API") if result.data else "Неизвестная ошибка"
        logger.error(f"Error fetching orders for shop: {error_msg}")
        await callback.answer(f"{SOM.ORDERS_LOAD_ERROR}: {error_msg}", show_alert=True)
        return

    data = result.data
    orders = data.get("items", [])
    total_count = data.get("total", 0)
    total_pages = max(1, (total_count + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE)

    # Фабрики для генерации callback_data кнопок внутри клавиатуры
    def callback_factory(action: str, p: int, order_id: int | None) -> str:
        if action == "order_detail":
            # Передаем контекст: откуда мы переходим в детали, чтобы вернуться назад корректно
            return ShopOrderDetailCallback(
                order_id=order_id,
                from_page=page,
                from_status=filter_status or "all",
            ).pack()
        elif action == "history":
            # Используем типизированный callback для пагинации
            return ShopOrdersListCallback(page=p, status=filter_status).pack()
        return "noop"

    def filter_callback_factory(status: str) -> str:
        # При переключении фильтра сбрасываем на 1 страницу
        return ShopOrdersListCallback(page=1, status=status).pack()

    keyboard = get_orders_list_keyboard(
        orders=orders,
        page=page,
        total_pages=total_pages,
        back_callback_data="shop_main_menu",
        callback_factory=callback_factory,
        filter_status=filter_status,
        filter_callback_factory=filter_callback_factory,
    )

    text = SOM.ORDERS_LIST_TITLE.format(total_count=total_count)

    # Используем suppress для игнорирования ошибки, если текст не изменился
    with suppress(Exception):
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(ShopOrderDetailCallback.filter())
async def shop_order_details_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: ShopOrderDetailCallback,
):
    """Отображает детали заказа."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success or not result.data:
        await callback.answer(SOM.ORDER_NOT_FOUND, show_alert=True)
        return

    order = result.data

    # Формирование текста
    text = format_order_details(order)

    # Формируем кнопку назад с учетом сохраненного состояния (страница, фильтр)
    back_callback = ShopOrdersListCallback(
        page=callback_data.from_page, status=callback_data.from_status
    ).pack()

    keyboard = get_order_details_keyboard(
        back_callback_data=back_callback,
        order_status=order.get("status"),
        cancel_callback_data=ShopOrderActionCallback(order_id=order_id, action="cancel").pack(),
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(ShopOrderActionCallback.filter(F.action == "cancel"))
async def shop_cancel_order_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: ShopOrderActionCallback,
):
    """Отменяет заказ."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    # Отправляем запрос на отмену
    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.update_order_status,
        order_id=order_id,
        status_data={"status": "CANCELED"},
    )

    if result.success:
        await callback.answer("Заказ успешно отменен", show_alert=True)
        # Обновляем детали заказа. При этом мы "имитируем" ShopOrderDetailCallback,
        # чтобы сохранить возможность вернуться назад.
        new_callback_data = ShopOrderDetailCallback(order_id=order_id)
        await shop_order_details_handler(
            callback, auth_client, orders_client, user_storage, new_callback_data
        )
    else:
        error_msg = (
            result.data.get("detail", "Неизвестная ошибка") if result.data else "Ошибка сети"
        )
        await callback.answer(f"Ошибка при отмене заказа: {error_msg}", show_alert=True)
