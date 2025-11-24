from aiogram import F, Router
from aiogram.types import CallbackQuery
from backend.src.common.enums import UserStatus
from bot.clients.auth_client import AuthClient
from bot.clients.shops_client import ShopsClient
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

    await callback.message.edit_text("Список магазинов:", reply_markup=keyboard)
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
    api_status = status_map.get(callback_data.filter)

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
        current_filter=callback_data.filter,
    )

    # Check if content changed to avoid "Message is not modified" error
    # But here we usually just edit. If it's the same, aiogram might raise error, but it's fine.
    try:
        await callback.message.edit_text("Список магазинов:", reply_markup=keyboard)
    except Exception:
        pass  # Ignore if not modified

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

        message_lines = [
            "📍 <b>Карточка магазина</b>\n",
            f"<b>Название:</b> {shop.name or 'Не указано'}",
            f"<b>Статус:</b> {status_emoji} {status_text}",
            f"<b>Telegram ID:</b> <code>{shop.telegram_id}</code>",
        ]

        if shop.username:
            message_lines.append(f"<b>Username:</b> @{shop.username}")

        if shop.address:
            message_lines.append(f"<b>Адрес:</b> {shop.address}")

        if shop.address_link:
            message_lines.append(f"<b>Ссылка на адрес:</b> {shop.address_link}")

        if shop.phone_numbers:
            phones = "\n".join([f"  • {phone}" for phone in shop.phone_numbers])
            message_lines.append(f"<b>Телефоны:</b>\n{phones}")

        text = "\n".join(message_lines)

        # Генерируем клавиатуру с кнопкой "Назад"
        keyboard = get_shop_card_keyboard(
            page=callback_data.page,
            current_filter=callback_data.filter,
        )

        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"❌ Ошибка при загрузке информации: {e!s}", show_alert=True)
