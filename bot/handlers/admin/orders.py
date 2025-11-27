from aiogram import F, Router
from aiogram.types import CallbackQuery
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.admin_client import AdminClient
from bot.clients.auth_client import AuthClient
from bot.filters.filters import RoleFilter
from bot.handlers.admin.messages import AdminMessages as AM
from bot.keyboards.orders import get_order_details_keyboard, get_orders_list_keyboard
from bot.redis_storage import UserDataStorage
from bot.utils.order_formatters import format_order_details
from bot.utils.token_manager import TokenManager

logger = get_logger(__name__)

router = Router(name="admin_orders_handlers")
router.message.filter(RoleFilter(UserRole.ADMIN))
router.callback_query.filter(RoleFilter(UserRole.ADMIN))

ORDERS_PER_PAGE = 5


@router.callback_query(F.data == "show_orders")
@router.callback_query(F.data.startswith("admin_orders_page_"))
@router.callback_query(F.data.startswith("admin_orders_filter_"))
async def show_orders_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Отображает список заказов с пагинацией и фильтрацией."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    # Парсинг параметров
    page = 1
    filter_status = None

    if callback.data.startswith("admin_orders_page_"):
        # admin_orders_page_{page}_{filter_status}
        parts = callback.data.split("_")
        page = int(parts[3])
        if len(parts) > 4 and parts[4] != "all":
            filter_status = parts[4]
    elif callback.data.startswith("admin_orders_filter_"):
        # admin_orders_filter_{status}
        status_str = callback.data.split("_")[-1]
        if status_str != "all":
            filter_status = status_str
        page = 1

    # Запрос к API
    api_status = None
    if filter_status == "completed":
        api_status = "completed"
    # Для active пока не передаем, так как нет такого статуса в Enum, а API не поддерживает группу.

    result = await admin_client.get_all_orders(
        token=token, page=page, limit=ORDERS_PER_PAGE, status=api_status
    )

    if result.status_code == 401:
        token = await token_manager.get_token(callback.from_user.id, force_refresh=True)
        if token:
            result = await admin_client.get_all_orders(
                token=token, page=page, limit=ORDERS_PER_PAGE, status=api_status
            )

    if not result.success:
        await callback.answer("Ошибка при получении заказов", show_alert=True)
        return

    data = result.data
    orders = data.get("items", [])
    total_count = data.get("total", 0)
    total_pages = max(1, (total_count + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE)

    def callback_factory(action: str, page: int, order_id: int | None) -> str:
        if action == "order_detail":
            return f"admin_order_select_{order_id}"
        elif action == "history":
            return f"admin_orders_page_{page}_{filter_status or 'all'}"
        return "noop"

    def filter_callback_factory(status: str) -> str:
        return f"admin_orders_filter_{status}"

    keyboard = get_orders_list_keyboard(
        orders=orders,
        page=page,
        total_pages=total_pages,
        back_callback_data="admin_back_to_menu",
        callback_factory=callback_factory,
        filter_status=filter_status,
        filter_callback_factory=filter_callback_factory,
    )

    text = AM.ORDERS_LIST_TITLE.format(total_count=total_count)

    if callback.message.text:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.startswith("admin_order_select_"))
async def order_details_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Отображает детали заказа."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    order_id = int(callback.data.split("_")[-1])
    result = await admin_client.get_order_details(token, order_id)

    if result.status_code == 401:
        token = await token_manager.get_token(callback.from_user.id, force_refresh=True)
        if token:
            result = await admin_client.get_order_details(token, order_id)

    if not result.success or not result.data:
        await callback.answer(AM.ORDER_NOT_FOUND, show_alert=True)
        return

    order = result.data

    # Формирование текста
    text = format_order_details(order)

    keyboard = get_order_details_keyboard(
        back_callback_data="show_orders",
        order_status=order.get("status"),
        cancel_callback_data=f"admin_order_cancel_{order_id}",
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_order_cancel_"))
async def cancel_order_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
):
    """Отменяет заказ."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    order_id = int(callback.data.split("_")[-1])

    # Отправляем запрос на отмену
    result = await admin_client.update_order(
        token=token, order_id=order_id, data={"status": "CANCELED"}
    )

    if result.status_code == 401:
        token = await token_manager.get_token(callback.from_user.id, force_refresh=True)
        if token:
            result = await admin_client.update_order(
                token=token, order_id=order_id, data={"status": "CANCELED"}
            )

    if result.success:
        await callback.answer("Заказ успешно отменен", show_alert=True)
        # Обновляем детали заказа
        # Трюк: вызываем order_details_handler, так как ID парсится одинаково
        await order_details_handler(callback, auth_client, admin_client, user_storage)
    else:
        error_msg = (
            result.data.get("detail", "Неизвестная ошибка") if result.data else "Ошибка сети"
        )
        await callback.answer(f"Ошибка при отмене заказа: {error_msg}", show_alert=True)
