from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.handlers.shop.messages import ShopMainKeyboardsButtons


def get_shop_main_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню магазина"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.REGISTRATION_CODE,
                    callback_data="get_registration_code_menu",
                )
            ],
            [InlineKeyboardButton(text=ShopMainKeyboardsButtons.SHOPS, callback_data="show_shops")],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.COURIERS, callback_data="show_couriers"
                )
            ],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.ORDERS, callback_data="show_orders"
                )
            ],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.DISPUTES, callback_data="show_disputes"
                )
            ],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.STATISTICS, callback_data="show_statistics"
                )
            ],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.EDIT_PROFILE,
                    callback_data="get_edit_profile_menu",
                )
            ],
        ]
    )
