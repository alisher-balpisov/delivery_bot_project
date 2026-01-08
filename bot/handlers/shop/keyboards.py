from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers.shop.messages import ShopMainKeyboardsButtons


def get_shop_main_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню магазина"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.CREATE_ORDER,
                    callback_data="create_order",
                ),
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.CURRENT_ORDERS,
                    callback_data="show_current_orders",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.ORDER_HISTORY,
                    callback_data="show_order_history",
                ),
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.STATISTICS,
                    callback_data="show_statistics",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.EDIT_PROFILE,
                    callback_data="edit_profile",
                )
            ],
        ]
    )
