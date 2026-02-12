"""Обработчики списка текущих заказов."""

from contextlib import suppress

from aiogram import F, Router
from aiogram.types import CallbackQuery
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.messages import OrderListMessages
from bot.handlers.shop.orders.callbacks import OrdersListCallback
from bot.keyboards.orders import get_orders_list_keyboard
from bot.redis_storage import UserDataStorage
from bot.utils.api_helper import execute_api_call
from bot.utils.token_manager import TokenManager

router = Router(name="shop_orders_list")

ORDERS_PER_PAGE = 5


@router.callback_query(F.data == "show_current_orders", RoleFilter(UserRole.SHOP))
@router.callback_query(OrdersListCallback.filter(), RoleFilter(UserRole.SHOP))
async def show_current_orders_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: OrdersListCallback | None = None,
):
    """Отображение списка заказов с пагинацией и фильтрацией."""
    # Если запущен через меню - создаем дефолтный объект
    if callback_data is None:
        callback_data = OrdersListCallback(page=1, status="all")

    page = callback_data.page
    filter_status = callback_data.status

    token_manager = TokenManager(auth_client, user_storage)

    # Маппинг фильтра в параметр API
    current = None
    if filter_status == "active":
        current = True
    elif filter_status == "completed":
        current = False

    # Выполняем запрос
    result = await execute_api_call(
        token_manager=token_manager,
        user_id=callback.from_user.id,
        func=orders_client.get_orders_history,
        page=page,
        limit=ORDERS_PER_PAGE,
        current=current,
    )

    if not result.success:
        error_msg = result.data.get("detail", "Ошибка API") if result.data else "Неизвестная ошибка"
        await callback.answer(f"{OrderListMessages.LOAD_ERROR}: {error_msg}", show_alert=True)
        return

    data = result.data
    orders = data.get("items", [])
    total_count = data.get("total", 0)
    total_pages = max(1, (total_count + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE)

    # Фабрики callback_data
    def callback_factory(action: str, p: int, order_id: int | None) -> str:
        from bot.handlers.shop.orders.callbacks import OrderDetailCallback

        if action == "order_detail":
            return OrderDetailCallback(
                order_id=order_id,
                from_page=page,
                from_status=filter_status or "all",
            ).pack()
        elif action == "history":
            return OrdersListCallback(page=p, status=filter_status).pack()
        return "noop"

    def filter_callback_factory(status: str) -> str:
        return OrdersListCallback(page=1, status=status).pack()

    keyboard = get_orders_list_keyboard(
        orders=orders,
        page=page,
        total_pages=total_pages,
        back_callback_data="shop_main_menu",
        callback_factory=callback_factory,
        filter_status=filter_status,
        filter_callback_factory=filter_callback_factory,
    )

    text = OrderListMessages.LIST_TITLE.format(total_count=total_count)

    # Используем suppress для игнорирования ошибки неизменённого текста
    with suppress(Exception):
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
