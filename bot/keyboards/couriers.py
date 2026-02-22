from enum import StrEnum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from backend.src.couriers.schemas import CourierListItem


class CourierFilter(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_SHIFT = "on_shift"
    ALL = "all"


class CouriersCallback(CallbackData, prefix="couriers"):
    action: str  # list, open, history
    page: int = 1
    list_page: int = 1
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
                        list_page=1,
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
                        list_page=page,
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
                    list_page=page - 1,
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
                    list_page=page + 1,
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
    back_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры для карточки курьера.

    Args:
        page: Номер текущей страницы списка
        current_filter: Текущий фильтр списка
        courier_id: ID курьера
        back_callback_data: Пользовательский callback для кнопки "Назад".
            Если не передан — возвращаемся к списку курьеров.
    """
    # Определяем callback для кнопки "Назад"
    if back_callback_data is None:
        back_callback_data = CouriersCallback(
            action="list",
            page=page,
            list_page=page,
            filter_type=current_filter,
        ).pack()

    keyboard = [
        [
            InlineKeyboardButton(
                text="📜 История заказов",
                callback_data=CouriersCallback(
                    action="history",
                    page=1,
                    list_page=page,
                    filter_type=current_filter,
                    courier_id=courier_id,
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


def get_couriers_list_for_stats_keyboard(
    couriers: list[CourierListItem],
    page: int,
    total_pages: int,
    current_filter: CourierFilter,
) -> InlineKeyboardMarkup:
    """Клавиатура списка курьеров для выбора в статистике.

    Аналог get_shops_list_for_stats_keyboard: использует отдельные
    action-ы (stats_list_couriers, stats_select_courier), чтобы
    не конфликтовать со стандартными хендлерами списка курьеров.
    """
    keyboard = []

    # 1. Фильтры
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
            display_text = f"✅ {text}" if filter_val == current_filter else text
            keyboard_row.append(
                InlineKeyboardButton(
                    text=display_text,
                    callback_data=CouriersCallback(
                        action="stats_list_couriers",
                        page=1,
                        list_page=1,
                        filter_type=filter_val,
                    ).pack(),
                )
            )
        keyboard.append(keyboard_row)

    # 2. Список курьеров — с action "stats_select_courier"
    for courier in couriers:
        status_emoji = "🟢" if courier.is_active else "🔴"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{status_emoji} {courier.full_name}",
                    callback_data=CouriersCallback(
                        action="stats_select_courier",
                        courier_id=courier.id,
                        page=page,
                        list_page=page,
                        filter_type=current_filter,
                    ).pack(),
                )
            ]
        )

    # 3. Пагинация
    pagination_row = []
    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=CouriersCallback(
                    action="stats_list_couriers",
                    page=page - 1,
                    list_page=page - 1,
                    filter_type=current_filter,
                ).pack(),
            )
        )

    pagination_row.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=CouriersCallback(
                    action="stats_list_couriers",
                    page=page + 1,
                    list_page=page + 1,
                    filter_type=current_filter,
                ).pack(),
            )
        )
    keyboard.append(pagination_row)

    # 4. Кнопка "Назад" — возврат в меню статистики
    keyboard.append(
        [
            InlineKeyboardButton(
                text="Назад",
                callback_data="show_statistics_admin",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
