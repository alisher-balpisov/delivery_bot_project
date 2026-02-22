# handlers_orders.py — Хендлеры списка заказов (для админа)
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
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


class OrdersListCallback(CallbackData, prefix="admin_orders"):
    page: int = 1
    status: str = "all"  # active, completed, all


class OrderDetailCallback(CallbackData, prefix="admin_order_det"):
    order_id: int
    from_page: int = 1
    from_status: str = "all"


class OrderActionCallback(CallbackData, prefix="admin_order_act"):
    order_id: int
    action: str  # cancel, etc.
    page: int = 1
    status: str = "all"


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


@router.callback_query(F.data == "show_orders")
@router.callback_query(OrdersListCallback.filter())
async def show_orders_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
    callback_data: OrdersListCallback | None = None,
):
    """Отображает список заказов с пагинацией и фильтрацией."""
    # Если запущен через "show_orders" (меню), создаем дефолтный объект
    if callback_data is None:
        callback_data = OrdersListCallback(page=1, status="all")

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
        func=admin_client.get_all_orders,
        page=page,
        limit=ORDERS_PER_PAGE,
        current=current,
    )

    if not result.success:
        # Пытаемся достать детальное описание ошибки, если есть
        error_msg = result.data.get("detail", "Ошибка API") if result.data else "Неизвестная ошибка"
        logger.error(f"Error fetching orders: {error_msg}")
        await callback.answer(f"Не удалось загрузить заказы: {error_msg}", show_alert=True)
        return

    data = result.data
    orders = data.get("items", [])
    total_count = data.get("total", 0)
    total_pages = max(1, (total_count + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE)

    # Фабрики для генерации callback_data кнопок внутри клавиатуры
    def callback_factory(action: str, p: int, order_id: int | None) -> str:
        if action == "order_detail":
            # Передаем контекст: откуда мы переходим в детали, чтобы вернуться назад корректно
            return OrderDetailCallback(
                order_id=order_id,
                from_page=page,
                from_status=filter_status or "all",
            ).pack()
        elif action == "history":
            # Используем типизированный callback для пагинации
            return OrdersListCallback(page=p, status=filter_status).pack()
        return "noop"

    def filter_callback_factory(status: str) -> str:
        # При переключении фильтра сбрасываем на 1 страницу
        return OrdersListCallback(page=1, status=status).pack()

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

    # Используем suppress для игнорирования ошибки, если текст не изменился
    with suppress(Exception):
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(OrderDetailCallback.filter())
async def order_details_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
    callback_data: OrderDetailCallback,
):
    """Отображает детали заказа."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        admin_client.get_order_details,
        order_id=order_id,
    )

    if not result.success or not result.data:
        await callback.answer(AM.ORDER_NOT_FOUND, show_alert=True)
        return

    order = result.data

    # Формирование текста
    text = format_order_details(order, role=UserRole.ADMIN.value)

    # Формируем кнопку назад с учетом сохраненного состояния (страница, фильтр)
    back_callback = OrdersListCallback(
        page=callback_data.from_page, status=callback_data.from_status
    ).pack()

    keyboard = get_order_details_keyboard(
        back_callback_data=back_callback,
        order_status=order.get("status"),
        cancel_callback_data=OrderActionCallback(
            order_id=order_id,
            action="cancel",
            page=callback_data.from_page,
            status=callback_data.from_status,
        ).pack(),
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(OrderActionCallback.filter(F.action == "cancel"))
async def cancel_order_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    admin_client: AdminClient,
    user_storage: UserDataStorage,
    callback_data: OrderActionCallback,
):
    """Отменяет заказ."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    # Отправляем запрос на отмену
    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        admin_client.update_order,
        order_id=order_id,
        data={"status": "CANCELED"},
    )

    if result.success:
        await callback.answer("Заказ успешно отменен", show_alert=True)
        # Обновляем детали заказа. При этом мы "имитируем" OrderDetailCallback,
        # чтобы сохранить возможность вернуться назад.
        # Для простоты можно просто перезагрузить текущее состояние.
        # Но так как мы находимся в OrderActionCallback, проще всего вызвать
        # обновление текста через get_order_details и новую клавиатуру.
        new_callback_data = OrderDetailCallback(
            order_id=order_id,
            from_page=callback_data.page,
            from_status=callback_data.status,
        )
        await order_details_handler(
            callback, auth_client, admin_client, user_storage, new_callback_data
        )
    else:
        error_msg = (
            result.data.get("detail", "Неизвестная ошибка") if result.data else "Ошибка сети"
        )
        await callback.answer(f"Ошибка при отмене заказа: {error_msg}", show_alert=True)
