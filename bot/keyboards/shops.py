from enum import StrEnum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from backend.src.shops.schemas import ShopListItem
from bot.messages import ShopMessages


class ShopFilter(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ALL = "all"


class ShopsCallback(CallbackData, prefix="shops"):
    action: str  # list, open, history
    page: int = 1
    filter_type: ShopFilter = ShopFilter.ACTIVE
    shop_id: int | None = None
    order_id: int | None = None


def get_shops_list_keyboard(
    shops: list[ShopListItem],
    page: int,
    total_pages: int,
    current_filter: ShopFilter,
) -> InlineKeyboardMarkup:
    keyboard = []

    # 1. Filter Buttons
    # Row 1: Active, Inactive
    # Row 2: All
    filter_rows = [
        [
            (ShopFilter.ACTIVE, "Активные"),
            (ShopFilter.INACTIVE, "Инактив"),
        ],
        [
            (ShopFilter.ALL, "Все"),
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
                    callback_data=ShopsCallback(
                        action="list",
                        page=1,  # Reset to page 1 on filter change
                        filter_type=filter_val,
                    ).pack(),
                )
            )
        keyboard.append(keyboard_row)

    # 2. Shop List
    for shop in shops:
        status_emoji = "🟢" if shop.status == "active" else "🔴"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{status_emoji} {shop.name or 'Без названия'}",
                    callback_data=ShopsCallback(
                        action="open",
                        shop_id=shop.id,
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
                callback_data=ShopsCallback(
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
                callback_data=ShopsCallback(
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
                callback_data="show_main_menu",  # Assuming this exists or handled
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_shop_card_keyboard(
    page: int,
    current_filter: ShopFilter,
    shop_id: int,
    back_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры для карточки магазина.

    Args:
        page: Номер текущей страницы списка
        current_filter: Текущий фильтр списка
        shop_id: ID магазина
        back_callback_data: Пользовательский callback для кнопки "Назад".
            Если не передан — возвращаемся к списку магазинов.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками "Назад" и "Главное меню"
    """
    # Определяем callback для кнопки "Назад"
    if back_callback_data is None:
        back_callback_data = ShopsCallback(
            action="list",
            page=page,
            filter_type=current_filter,
        ).pack()

    keyboard = [
        [
            InlineKeyboardButton(
                text="📜 История заказов",
                callback_data=ShopsCallback(
                    action="history",
                    page=1,
                    filter_type=current_filter,
                    shop_id=shop_id,
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="Назад",
                callback_data=back_callback_data,
            ),
            InlineKeyboardButton(
                text="Главное меню",
                callback_data="show_main_menu",
            ),
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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
