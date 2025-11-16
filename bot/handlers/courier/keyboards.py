from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.handlers.courier.messages import CourierMainKeyboardsButtons


def get_courier_main_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню курьера."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=CourierMainKeyboardsButtons.START_SHIFT,
                    callback_data = "start_shift"
                )
            ],
            [
                InlineKeyboardButton(
                    text=CourierMainKeyboardsButtons.CURRENT_ORDERS,
                    callback_data = "get_current_orders"
                )
            ],
            [
                InlineKeyboardButton(
                    text=CourierMainKeyboardsButtons.ORDERS_HISTORY,
                    callback_data = "get_order_history"
                )
            ],
            [
                InlineKeyboardButton(
                    text=CourierMainKeyboardsButtons.DISPUTES,
                    callback_data = "get_disputes"
                )
            ],
            [
                InlineKeyboardButton(
                    text=CourierMainKeyboardsButtons.EDIT_PROFILE,
                    callback_data = "edit_profile_menu"
                )
            ]
        ]
)
