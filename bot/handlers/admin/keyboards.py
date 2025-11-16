from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.handlers.admin.messages import AdminMainButtons, AdminRegistrationCodesMenuButtons


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню администратора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.REGISTARATION_CODE,
                    callback_data = "get_registration_code_menu"
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.SHOPS,
                    callback_data = "show_shops"
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.COURIERS,
                    callback_data = "show_couriers"
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.ORDERS,
                    callback_data = "show_orders"
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.DISPUTES,
                    callback_data = "show_disputes"
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.STATISTICS,
                    callback_data = "show_statistics"
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.EDIT_PROFILE,
                    callback_data = "get_edit_profile_menu"
                )
            ],
        ]
)

def get_registration_code_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура меню 'Код регистрации'"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AdminRegistrationCodesMenuButtons.CREATE_CODE_FOR_COURIER,
                    callback_data="admin_create_code_courier"
                ),
                InlineKeyboardButton(
                    text=AdminRegistrationCodesMenuButtons.CREATE_CODE_FOR_SHOP,
                    callback_data="admin_create_code_shop"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=AdminRegistrationCodesMenuButtons.VIEW_REGISTRATION_CODES,
                    callback_data="admin_view_codes"
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminRegistrationCodesMenuButtons.BACK,
                    callback_data="admin_back_to_menu"
                )
            ]
        ]
    )