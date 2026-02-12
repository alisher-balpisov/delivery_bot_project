# handlers_current_orders.py — Хендлеры просмотра заказов для магазина
import html
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import OrderStatus, UserRole
from backend.src.core.logging import get_logger

from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards import get_shop_edit_menu_keyboard, get_shop_order_details_keyboard
from bot.handlers.shop.messages import ShopOrder
from bot.handlers.shop.messages import ShopOrdersMessages as SOM
from bot.handlers.shop.service import ShopOrderActionCallback, validate_price
from bot.handlers.shop.states import OrderActionStates
from bot.keyboards.admin import InlineKeyboardBuilder
from bot.keyboards.orders import get_orders_list_keyboard
from bot.redis_storage import UserDataStorage
from bot.utils.api_helper import execute_api_call
from bot.utils.formatters import format_courier_card
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


async def _initiate_edit(
    callback: CallbackQuery,
    state: FSMContext,
    target_state: Any,
    prompt_message: str,
):
    """Универсальная функция для старта редактирования поля."""
    order_id = ShopOrderActionCallback.unpack(callback.data).order_id
    await state.set_state(target_state)
    await state.update_data(order_id=order_id)
    await callback.message.answer(prompt_message, parse_mode="HTML")
    await callback.answer()


async def _process_api_update(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
    func: Callable[..., Any],
    success_message: str,
    **kwargs: Any,
):
    """Универсальная функция для выполнения API-запроса на обновление заказа."""
    data = await state.get_data()
    order_id = data.get("order_id")
    token_manager = TokenManager(auth_client, user_storage)

    result = await execute_api_call(
        token_manager,
        message.from_user.id,
        func,
        order_id=order_id,
        **kwargs,
    )

    if result.success:
        await message.answer(success_message)
        await state.clear()
    else:
        # Пытаемся получить detail
        detail = result.detail or (
            result.data.get("detail") if result.data else "Неизвестная ошибка"
        )
        escaped_detail = html.escape(str(detail))
        await message.answer(f"❌ Ошибка: {escaped_detail}")


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

    keyboard = get_shop_order_details_keyboard(
        order_id=order_id,
        status=order.get("status"),
        back_callback=back_callback,
        courier_id=order.get("courier_id")
        or (order.get("courier").get("id") if order.get("courier") else None),
        dispute_id=order.get("dispute_id"),
        has_price=order.get("price") is not None,
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
        orders_client.update_order,
        order_id=order_id,
        data={"status": OrderStatus.CANCELED.value},
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


@router.callback_query(ShopOrderActionCallback.filter(F.action == "complete"))
async def shop_complete_order_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: ShopOrderActionCallback,
):
    """Подтверждает завершение заказа."""
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.update_order,
        order_id=order_id,
        data={"status": OrderStatus.COMPLETED.value},
    )

    if result.success:
        await callback.answer("✅ Заказ успешно завершен", show_alert=True)
        # Возвращаемся в детали
        new_callback_data = ShopOrderDetailCallback(order_id=order_id)
        await shop_order_details_handler(
            callback, auth_client, orders_client, user_storage, new_callback_data
        )
    else:
        error_msg = result.detail or "Ошибка при завершении заказа"
        await callback.answer(f"❌ {error_msg}", show_alert=True)


@router.callback_query(ShopOrderActionCallback.filter(F.action == "set_price"))
async def shop_set_price_handler(
    callback: CallbackQuery,
    state: FSMContext,
    callback_data: ShopOrderActionCallback,
):
    """Инициирует процесс установки цены."""
    await _initiate_edit(
        callback,
        state,
        OrderActionStates.waiting_for_price,
        "💰 <b>Укажите стоимость доставки</b>\n\n"
        "Введите сумму в тенге (только цифры).\n"
        "<i>Минимальная стоимость: 3000 ₸</i>",
    )


@router.callback_query(ShopOrderActionCallback.filter(F.action == "add_note"))
async def shop_add_note_handler(
    callback: CallbackQuery,
    state: FSMContext,
    callback_data: ShopOrderActionCallback,
):
    """Инициирует процесс добавления заметки."""
    await _initiate_edit(
        callback,
        state,
        OrderActionStates.waiting_for_note,
        "📝 <b>Добавление заметки к заказу</b>\n\nВведите текст заметки. Она будет видна курьеру.",
    )


@router.message(OrderActionStates.waiting_for_price)
async def process_order_price_update(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Обрабатывает ввод новой цены."""
    price, error = validate_price(message.text)
    if error:
        await message.answer(error)
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    await _process_api_update(
        message,
        state,
        auth_client,
        user_storage,
        orders_client.update_order,
        f"✅ Цена заказа #{order_id} установлена: {price} ₸",
        data={"price": price},
    )


@router.message(OrderActionStates.waiting_for_note)
async def process_order_note_add(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Обрабатывает ввод заметки."""
    content = message.text.strip()
    if not content:
        await message.answer("⚠️ Текст заметки не может быть пустым.")
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    await _process_api_update(
        message,
        state,
        auth_client,
        user_storage,
        orders_client.add_order_note,
        f"✅ Заметка к заказу #{order_id} добавлена.",
        content=content,
    )


@router.callback_query(ShopOrderActionCallback.filter(F.action == "view_courier"))
async def shop_view_courier_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: ShopOrderActionCallback,
):
    """Отображает информацию о курьере."""
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
    courier = order.get("courier")

    if not courier:
        await callback.answer("Курьер не назначен", show_alert=True)
        return

    text = format_courier_card(courier)

    # Кнопка назад возвращает к деталям заказа
    back_callback = ShopOrderDetailCallback(order_id=order_id).pack()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(ShopOrderActionCallback.filter(F.action == "edit"))
async def shop_edit_order_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: ShopOrderActionCallback,
):
    """Меню редактирования заказа."""
    await state.clear()  # Сбрасываем любые активные состояния редактирования
    token_manager = TokenManager(auth_client, user_storage)
    order_id = callback_data.order_id

    # Получаем заказ, чтобы проверить статус
    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success:
        await callback.answer("Не удалось загрузить заказ", show_alert=True)
        return

    order = result.data
    status = order.get("status")

    # Определяем доступность действий
    # Цену можно менять всегда, пока заказ активен (проверка была на уровне кнопки в orders_details)
    # Адрес можно менять пока курьер не забрал заказ (например, до DELIVERING)
    # Но для простоты разрешим менять адрес если статус не DELIVERING/COMPLETED/CANCELED
    # TODO: Уточнить бизнес-логику по статусам. Пока берем PENDING, PENDING_COURIER, COURIER_EN_ROUTE
    can_edit_address = status in [
        OrderStatus.PENDING.value,
        OrderStatus.PENDING_COURIER.value,
        OrderStatus.COURIER_EN_ROUTE.value,
    ]

    back_callback = ShopOrderDetailCallback(order_id=order_id).pack()

    keyboard = get_shop_edit_menu_keyboard(
        order_id=order_id,
        back_callback=back_callback,
        can_edit_price=True,
        can_edit_address=can_edit_address,
        can_edit_description=True,
        can_edit_courier=False,  # Пока отключаем возможность смены курьера, нужна логика выбора
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование заказа #{order_id}</b>\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(ShopOrderActionCallback.filter(F.action == "edit_address"))
async def shop_edit_address_handler(
    callback: CallbackQuery,
    state: FSMContext,
    callback_data: ShopOrderActionCallback,
):
    """Инициирует процесс изменения адреса."""
    await _initiate_edit(
        callback,
        state,
        OrderActionStates.waiting_for_address,
        ShopOrder.EDIT_ADDRESS_PROMPT,
    )


@router.message(OrderActionStates.waiting_for_address)
async def process_order_address_update(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Обрабатывает ввод нового адреса."""
    new_address = message.text.strip()
    if len(new_address) < 5:
        await message.answer("⚠️ Адрес слишком короткий. Пожалуйста, укажите точный адрес.")
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    await _process_api_update(
        message,
        state,
        auth_client,
        user_storage,
        orders_client.update_order,
        f"✅ Адрес заказа #{order_id} обновлен.",
        data={"recipient_address": new_address},
    )


@router.callback_query(ShopOrderActionCallback.filter(F.action == "edit_order_description"))
async def shop_edit_description_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
    callback_data: ShopOrderActionCallback,
):
    """Инициирует процесс изменения описания с предпросмотром текущего."""
    order_id = callback_data.order_id
    token_manager = TokenManager(auth_client, user_storage)

    # Получаем текущие данные заказа
    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success:
        await callback.answer("Не удалось загрузить данные заказа", show_alert=True)
        return

    order = result.data
    current_description = order.get("description", "")

    text = (
        "<b>✏️ Изменение описания заказа</b>\n"
        f"<b>Текущее описание:</b>\n<blockquote>{html.escape(current_description)}</blockquote>\n\n"
        "<i>Введите новое описание заказа:</i>"
    )

    # Кнопка отмены возвращает в меню редактирования
    cancel_callback = ShopOrderActionCallback(order_id=order_id, action="edit").pack()

    await callback.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data=cancel_callback,
                    )
                ]
            ]
        ),
        parse_mode="HTML",
    )

    await state.set_state(OrderActionStates.waiting_for_description)
    await state.update_data(order_id=order_id)
    await callback.answer()


@router.message(OrderActionStates.waiting_for_description)
async def process_order_description_update(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Обрабатывает ввод нового описания."""
    new_description = message.text.strip()
    if not new_description:
        await message.answer("⚠️ Описание не может быть пустым.")
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    token_manager = TokenManager(auth_client, user_storage)

    # Обновляем описание
    result = await execute_api_call(
        token_manager,
        message.from_user.id,
        orders_client.update_order,
        order_id=order_id,
        data={"description": new_description},
    )

    if not result.success:
        error_msg = result.detail or (
            result.data.get("detail") if result.data else "Неизвестная ошибка"
        )
        await message.answer(f"❌ Ошибка при обновлении описания: {html.escape(str(error_msg))}")
        return

    # Получаем обновленные детали заказа
    result = await execute_api_call(
        token_manager,
        message.from_user.id,
        orders_client.get_order_details,
        order_id=order_id,
    )

    if not result.success or not result.data:
        await message.answer("✅ Описание обновлено, но не удалось загрузить детали заказа.")
        await state.clear()
        return

    order = result.data

    # Формируем карточку заказа
    text = format_order_details(order)

    # Кнопка "Назад" ведет в список заказов (по умолчанию 1 страница, все)
    back_callback = ShopOrdersListCallback(page=1, status="all").pack()

    keyboard = get_shop_order_details_keyboard(
        order_id=order_id,
        status=order.get("status"),
        back_callback=back_callback,
        courier_id=order.get("courier_id")
        or (order.get("courier").get("id") if order.get("courier") else None),
        dispute_id=order.get("dispute_id"),
        has_price=order.get("price") is not None,
    )

    await message.answer(
        f"✅ Описание обновлено.\n\n{text}", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(ShopOrderActionCallback.filter(F.action == "change_courier"))
async def shop_change_courier_handler(callback: CallbackQuery):
    """Заглушка для смены курьера."""
    await callback.answer("Функция смены курьера в разработке", show_alert=True)


@router.callback_query(
    ShopOrderActionCallback.filter(F.action.in_(["view_dispute", "open_dispute"]))
)
async def shop_action_placeholder_handler(callback: CallbackQuery):
    """Заглушка для действий, которые будут реализованы позже."""
    await callback.answer("Этот функционал будет доступен в ближайшем обновлении", show_alert=True)
