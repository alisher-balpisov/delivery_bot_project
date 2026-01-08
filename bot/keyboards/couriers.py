from enum import StrEnum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.constants import CourierListItem


class CourierFilter(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_SHIFT = "on_shift"
    ALL = "all"


class CouriersCallback(CallbackData, prefix="couriers"):
    action: str  # list, open, history
    page: int = 1
    filter_type: CourierFilter = CourierFilter.ACTIVE
    courier_id: int | None = None
    order_id: int | None = None


def get_couriers_list_keyboard(
    couriers: list[CourierListItem],
    page: int,
    total_pages: int,
    current_filter: CourierFilter,
) -> InlineKeyboardMarkup:
    keyboard = []

    # 1. Filter Buttons
    # Row 1: Active, Inactive
    # Row 2: On Shift, All
    filter_rows = [
        [
            (CourierFilter.ACTIVE, "Активные"),
            (CourierFilter.INACTIVE, "Инактив"),
        ],
        [
            (CourierFilter.ON_SHIFT, "На смене"),
            (CourierFilter.ALL, "Все"),
        ],
    ]

    for row in filter_rows:
        keyboard_row = []
        for filter_val, text in row:
            # Mark selected filter
            display_text = f"✅ {text}" if filter_val == current_filter else text
            keyboard_row.append(
                InlineKeyboardButton(
                    text=display_text,
                    callback_data=CouriersCallback(
                        action="list",
                        page=1,  # Reset to page 1 on filter change
                        filter_type=filter_val,
                    ).pack(),
                )
            )
        keyboard.append(keyboard_row)

    # 2. Courier List
    for courier in couriers:
        status_emoji = "🟢" if courier.is_active else "🔴"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{status_emoji} {courier.full_name}",
                    callback_data=CouriersCallback(
                        action="open",
                        courier_id=courier.id,
                        page=page,
                        filter_type=current_filter,
                    ).pack(),
                )
            ]
        )

    # 3. Pagination
    pagination_row = []
    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=CouriersCallback(
                    action="list",
                    page=page - 1,
                    filter_type=current_filter,
                ).pack(),
            )
        )

    pagination_row.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="noop",  # Non-clickable
        )
    )

    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=CouriersCallback(
                    action="list",
                    page=page + 1,
                    filter_type=current_filter,
                ).pack(),
            )
        )
    keyboard.append(pagination_row)

    # 4. Back Button
    keyboard.append(
        [
            InlineKeyboardButton(
                text="Назад",
                callback_data="show_main_menu",  # Assuming this exists
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_courier_card_keyboard(
    page: int,
    current_filter: CourierFilter,
    courier_id: int,
) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры для карточки курьера.

    Args:
        page: Номер текущей страницы списка
        current_filter: Текущий фильтр списка
        courier_id: ID курьера
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="📜 История заказов",
                callback_data=CouriersCallback(
                    action="history",
                    page=1,
                    filter_type=current_filter,
                    courier_id=courier_id,
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="Назад",
                callback_data=CouriersCallback(
                    action="list",
                    page=page,
                    filter_type=current_filter,
                ).pack(),
            ),
            InlineKeyboardButton(
                text="Главное меню",
                callback_data="show_main_menu",
            ),
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
