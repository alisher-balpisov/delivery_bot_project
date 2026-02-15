"""Обработчики главного меню магазина."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import UserRole

from bot.clients import DisputesClient
from bot.clients.auth_client import AuthClient
from bot.clients.shops_client import ShopsClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards.main import get_back_to_menu_keyboard, get_main_menu_keyboard
from bot.handlers.shop.messages import MainMenuMessages
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

router = Router(name="shop_main")


@router.message(Command("start"), RoleFilter(UserRole.SHOP))
async def main_menu_handler(
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

    text = MainMenuMessages.MAIN_MENU.format(
        active_orders=stats.active_orders,
        today_orders=stats.orders_today,
        active_disputes=stats.active_disputes,
    )

    await message.answer(text, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "shop_main_menu", RoleFilter(UserRole.SHOP))
async def main_menu_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Возврат в главное меню через callback."""
    await state.clear()

    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    stats = await shops_client.get_shop_stats(token)

    text = MainMenuMessages.MAIN_MENU.format(
        active_orders=stats.active_orders,
        today_orders=stats.orders_today,
        active_disputes=stats.active_disputes,
    )

    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "show_my_disputes", RoleFilter(UserRole.SHOP))
async def show_my_disputes_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    user_storage: UserDataStorage,
    state: FSMContext,
):
    """Отображение списка споров магазина."""
    from bot.handlers.shop.orders.dispute.list import dispute_list_handler

    await dispute_list_handler(callback, auth_client, disputes_client, user_storage, page=1)


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

    text = MainMenuMessages.STATISTICS.format(
        active_orders=stats.active_orders,
        orders_today=stats.orders_today,
        active_disputes=stats.active_disputes,
    )

    keyboard = get_back_to_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
