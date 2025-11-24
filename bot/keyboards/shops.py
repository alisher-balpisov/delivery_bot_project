from enum import StrEnum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from backend.src.shops.schemas import ShopListItem


class ShopFilter(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ALL = "all"


class ShopsCallback(CallbackData, prefix="shops"):
    action: str  # list, open
    page: int = 1
    filter: ShopFilter = ShopFilter.ACTIVE
    shop_id: int | None = None


def get_shops_list_keyboard(
    shops: list[ShopListItem],
    page: int,
    total_pages: int,
    current_filter: ShopFilter,
) -> InlineKeyboardMarkup:
    keyboard = []

    # 1. Filter Buttons
    filter_row = []
    filters = [
        (ShopFilter.ACTIVE, "Активные"),
        (ShopFilter.INACTIVE, "Инактив"),
        (ShopFilter.ALL, "Все"),
    ]

    for filter_val, text in filters:
        # Mark selected filter
        display_text = f"✅ {text}" if filter_val == current_filter else text
        filter_row.append(
            InlineKeyboardButton(
                text=display_text,
                callback_data=ShopsCallback(
                    action="list",
                    page=1,  # Reset to page 1 on filter change
                    filter=filter_val,
                ).pack(),
            )
        )
    keyboard.append(filter_row)

    # 2. Shop List
    for shop in shops:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{shop.name or 'Без названия'}",
                    callback_data=ShopsCallback(
                        action="open",
                        shop_id=shop.id,
                        page=page,
                        filter=current_filter,
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
                    filter=current_filter,
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
                    filter=current_filter,
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
) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры для карточки магазина.

    Args:
        page: Номер текущей страницы списка
        current_filter: Текущий фильтр списка

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками "Назад" и "Главное меню"
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="Назад",
                callback_data=ShopsCallback(
                    action="list",
                    page=page,
                    filter=current_filter,
                ).pack(),
            ),
            InlineKeyboardButton(
                text="Главное меню",
                callback_data="show_main_menu",
            ),
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
