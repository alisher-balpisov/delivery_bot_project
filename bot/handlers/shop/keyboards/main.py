"""Клавиатуры главного меню магазина."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers.shop.messages import MainMenuButtons


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню магазина."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=MainMenuButtons.CREATE_ORDER,
                    callback_data="create_order",
                ),
                InlineKeyboardButton(
                    text=MainMenuButtons.CURRENT_ORDERS,
                    callback_data="show_current_orders",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=MainMenuButtons.ORDER_HISTORY,
                    callback_data="show_order_history",
                ),
                InlineKeyboardButton(
                    text=MainMenuButtons.STATISTICS,
                    callback_data="show_statistics",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=MainMenuButtons.EDIT_PROFILE,
                    callback_data="edit_profile",
                ),
                InlineKeyboardButton(
                    text=MainMenuButtons.MY_DISPUTES,
                    callback_data="show_my_disputes",
                ),
            ],
        ]
    )


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Главное меню",
                    callback_data="shop_main_menu",
                )
            ]
        ]
    )


def get_profile_edit_keyboard() -> InlineKeyboardMarkup:
    """Меню редактирования профиля."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название магазина", callback_data="edit_shop_name")],
            [InlineKeyboardButton(text="📍 Адрес", callback_data="edit_shop_address")],
            [InlineKeyboardButton(text="📞 Телефон", callback_data="edit_shop_phone")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="shop_main_menu")],
        ]
    )
