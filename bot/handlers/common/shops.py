from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from backend.src.common.enums import UserStatus
from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.clients.shops_client import ShopsClient
from bot.handlers.admin.couriers import logger
from bot.keyboards.orders import get_order_details_keyboard, get_orders_list_keyboard
from bot.keyboards.shops import (
    ShopFilter,
    ShopsCallback,
    get_shop_card_keyboard,
    get_shops_list_keyboard,
)
from bot.redis_storage import UserDataStorage
from bot.utils.order_formatters import format_order_details
from bot.utils.token_manager import TokenManager

shops_router = Router(name="shops_handlers")


@shops_router.callback_query(F.data == "show_shops")
async def show_shops_handler(
    callback: CallbackQuery,
    shops_client: ShopsClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Показать список магазинов (первая страница, активные)."""
    # Get token
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    # Fetch shops
    response = await shops_client.get_shops(
        token=token,
        page=1,
        limit=10,
        status=UserStatus.ACTIVE,
    )

    keyboard = get_shops_list_keyboard(
        shops=response.items,
        page=response.page,
        total_pages=response.pages,
        current_filter=ShopFilter.ACTIVE,
    )

    text = f"🏪 <b>Список магазинов</b>\nВсего: {response.total}"
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@shops_router.callback_query(ShopsCallback.filter(F.action == "list"))
async def shops_navigation_handler(
    callback: CallbackQuery,
    callback_data: ShopsCallback,
    shops_client: ShopsClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Навигация по списку магазинов (пагинация, фильтры)."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    # Map filter enum to status string for API
    status_map = {
        ShopFilter.ACTIVE: UserStatus.ACTIVE,
        ShopFilter.INACTIVE: UserStatus.INACTIVE,
        ShopFilter.ALL: None,
    }
    api_status = status_map.get(callback_data.filter_type)

    response = await shops_client.get_shops(
        token=token,
        page=callback_data.page,
        limit=10,
        status=api_status,
    )

    keyboard = get_shops_list_keyboard(
        shops=response.items,
        page=response.page,
        total_pages=response.pages,
        current_filter=callback_data.filter_type,
    )

    text = f"🏪 <b>Список магазинов</b>\nВсего: {response.total}"

    # Check if content changed to avoid "Message is not modified" error
    # Но здесь обычно просто редактируем. Если сообщение не изменилось, aiogram может бросить ошибку.
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.exception("Failed to edit shop list message: %s", e)

    await callback.answer()


@shops_router.callback_query(ShopsCallback.filter(F.action == "open"))
async def open_shop_handler(
    callback: CallbackQuery,
    callback_data: ShopsCallback,
    shops_client: ShopsClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Открыть карточку магазина."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    try:
        # Получаем детальную информацию о магазине
        shop = await shops_client.get_shop_by_id(
            token=token,
            shop_id=callback_data.shop_id,
        )

        # Формируем текст сообщения
        status_emoji = "🟢" if shop.status == UserStatus.ACTIVE else "🔴"
        status_text = "Активен" if shop.status == UserStatus.ACTIVE else "Неактивен"

        username_text = f"@{shop.username}" if shop.username else "Нет"
        phones = ", ".join(shop.phone_numbers) if shop.phone_numbers else "Нет"

        text = (
            f"🏪 <b>Магазин: {shop.name or 'Не указано'}</b>\n\n"
            f"📱 Телеграм: {username_text}\n"
            f"📞 Телефон: {phones}\n"
            f"📍 Адрес: {shop.address or 'Не указано'}\n"
            f"🔗 Ссылка на адрес: {shop.address_link or 'Нет'}\n"
            f"🔒 Статус: {status_emoji} {status_text}\n"
        )

        # Генерируем клавиатуру с кнопкой "Назад"
        keyboard = get_shop_card_keyboard(
            page=callback_data.page,
            current_filter=callback_data.filter_type,
            shop_id=callback_data.shop_id,
        )

        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"❌ Ошибка при загрузке информации: {e!s}", show_alert=True)


@shops_router.callback_query(ShopsCallback.filter(F.action == "history"))
async def shop_history_handler(
    callback: CallbackQuery,
    callback_data: ShopsCallback,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Показать историю заказов магазина."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    shop_id = callback_data.shop_id
    page = callback_data.page
    limit = 5

    result = await orders_client.get_orders_history(
        token=token,
        page=page,
        limit=limit,
        shop_id=shop_id,
    )

    if not result.success:
        await callback.answer("Не удалось загрузить историю заказов", show_alert=True)
        return

    data = result.data
    orders = data.get("items", [])
    total = data.get("total", 0)
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    if not orders:
        text = "📭 История заказов пуста"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Назад",
                        callback_data=ShopsCallback(
                            action="open",
                            shop_id=shop_id,
                            page=1,
                            filter_type=callback_data.filter_type,
                        ).pack(),
                    )
                ]
            ]
        )
    else:
        text = f"📜 <b>История заказов (Всего: {total})</b>\nВыберите заказ для просмотра деталей:"

        def callback_factory(action: str, page: int, order_id: int | None) -> str:
            return ShopsCallback(
                action=action,
                shop_id=shop_id,
                page=page,
                filter_type=callback_data.filter_type,
                order_id=order_id,
            ).pack()

        back_callback = ShopsCallback(
            action="open",
            shop_id=shop_id,
            page=1,
            filter_type=callback_data.filter_type,
        ).pack()

        keyboard = get_orders_list_keyboard(
            orders=orders,
            page=page,
            total_pages=total_pages,
            back_callback_data=back_callback,
            callback_factory=callback_factory,
        )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@shops_router.callback_query(ShopsCallback.filter(F.action == "order_detail"))
async def shop_order_detail_handler(
    callback: CallbackQuery,
    callback_data: ShopsCallback,
    auth_client: AuthClient,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Показать детали заказа."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    order_id = callback_data.order_id

    result = await orders_client.get_order_details(token, order_id)

    if not result.success:
        await callback.answer("Не удалось загрузить детали заказа", show_alert=True)
        return

    order = result.data

    # Формирование текста деталей заказа с использованием унифицированного форматтера
    text = format_order_details(order)

    back_callback = ShopsCallback(
        action="history",
        shop_id=callback_data.shop_id,
        page=callback_data.page,
        filter_type=callback_data.filter_type,
    ).pack()

    keyboard = get_order_details_keyboard(back_callback_data=back_callback)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
