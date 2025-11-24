from aiogram import F, Router
from aiogram.types import CallbackQuery
from backend.src.common.enums import UserStatus
from bot.clients.auth_client import AuthClient
from bot.clients.shops_client import ShopsClient
from bot.handlers.admin.couriers import logger  # импортируем общий логгер
from bot.keyboards.shops import (
    ShopFilter,
    ShopsCallback,
    get_shop_card_keyboard,
    get_shops_list_keyboard,
)
from bot.redis_storage import UserDataStorage
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
        )

        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"❌ Ошибка при загрузке информации: {e!s}", show_alert=True)
