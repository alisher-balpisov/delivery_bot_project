from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.messages import AdminKeyboardMessages, ShopMessages


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню администратора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AdminKeyboardMessages.CREATE_CODE, callback_data="admin_create_code"
                ),
                InlineKeyboardButton(
                    text=AdminKeyboardMessages.VIEW_CODES, callback_data="admin_view_codes"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=AdminKeyboardMessages.STATS, callback_data="system_stats"
                ),
            ],
        ]
    )


def get_role_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора роли"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AdminKeyboardMessages.SHOP, callback_data="admin_create_code_shop"
                ),
                InlineKeyboardButton(
                    text=AdminKeyboardMessages.COURIER, callback_data="admin_create_code_courier"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=AdminKeyboardMessages.BACK, callback_data="admin_back_to_menu"
                )
            ],
        ]
    )


def get_order_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения заказа"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ShopMessages.CONFIRM_ORDER, callback_data="order_confirm"
                ),
                InlineKeyboardButton(text=ShopMessages.CANCEL_ORDER, callback_data="order_cancel"),
            ]
        ]
    )


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возврата в главное меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AdminKeyboardMessages.BACK, callback_data="admin_back_to_menu"
                )
            ]
        ]
    )
