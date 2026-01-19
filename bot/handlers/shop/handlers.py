# handlers.py — Меню магазина, профиль
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.shops_client import ShopsClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards import get_shop_main_keyboard, back_to_menu
from bot.handlers.shop.messages import ShopMessages
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

router = Router(name="shop_main_handlers")


@router.message(Command("start"), RoleFilter(UserRole.SHOP))
async def shop_main_menu_handler(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Главное меню магазина."""
    await state.clear()

    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(message.from_user.id)

    stats = await shops_client.get_shop_stats(token)

    text = ShopMessages.MAIN_MENU.format(
        active_orders=stats.active_orders,
        today_orders=stats.orders_today,
        active_disputes=stats.active_disputes,
    )

    await message.answer(text, reply_markup=get_shop_main_keyboard())


@router.callback_query(F.data == "shop_main_menu", RoleFilter(UserRole.SHOP))
async def shop_main_menu_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Возврат в главное меню магазина (через inline-кнопку)."""
    await state.clear()

    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    stats = await shops_client.get_shop_stats(token)

    text = ShopMessages.MAIN_MENU.format(
        active_orders=stats.active_orders,
        today_orders=stats.orders_today,
        active_disputes=stats.active_disputes,
    )

    await callback.message.edit_text(text, reply_markup=get_shop_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "show_statistics", RoleFilter(UserRole.SHOP))
async def show_statistics_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Показать статистику магазина."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    stats = await shops_client.get_shop_stats(token)

    text = (
        "📊 <b>Статистика магазина</b>\n\n"
        f"📦 Активные заказы: {stats.active_orders}\n"
        f"📅 Заказов сегодня: {stats.orders_today}\n"
        f"⚠️ Активные споры: {stats.active_disputes}\n"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="shop_main_menu")]]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "edit_profile", RoleFilter(UserRole.SHOP))
async def edit_profile_handler(callback: CallbackQuery):
    """Показать меню редактирования профиля магазина."""
    text = "⚙️ <b>Редактирование профиля</b>\n\nВыберите, что хотите изменить:"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название магазина", callback_data="edit_shop_name")],
            [InlineKeyboardButton(text="📍 Адрес", callback_data="edit_shop_address")],
            [InlineKeyboardButton(text="📞 Телефон", callback_data="edit_shop_phone")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="shop_main_menu")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "create_order", RoleFilter(UserRole.SHOP))
async def create_order_handler(callback: CallbackQuery):
    text = """Введите информацию о заказе 
номер получателя 
адрес
дополнительную информацию
(или вставьте сообщение которое вам отправил заказчик)

Детали заказа всегда можно дополнить или изменить*
"""
    keyboard = back_to_menu()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()