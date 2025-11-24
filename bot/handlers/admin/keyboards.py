from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.handlers.admin.messages import AdminMainButtons, AdminRegistrationCodesMenuButtons


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню администратора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.REGISTARATION_CODE,
                    callback_data="get_registration_code_menu",
                )
            ],
            [InlineKeyboardButton(text=AdminMainButtons.SHOPS, callback_data="show_shops")],
            [InlineKeyboardButton(text=AdminMainButtons.COURIERS, callback_data="show_couriers")],
            [InlineKeyboardButton(text=AdminMainButtons.ORDERS, callback_data="show_orders")],
            [InlineKeyboardButton(text=AdminMainButtons.DISPUTES, callback_data="show_disputes")],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.STATISTICS, callback_data="show_statistics"
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.EDIT_PROFILE, callback_data="get_edit_profile_menu"
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
                    callback_data="admin_create_code_courier",
                ),
                InlineKeyboardButton(
                    text=AdminRegistrationCodesMenuButtons.CREATE_CODE_FOR_SHOP,
                    callback_data="admin_create_code_shop",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=AdminRegistrationCodesMenuButtons.VIEW_REGISTRATION_CODES,
                    callback_data="admin_view_codes",
                )
            ],
            [
                InlineKeyboardButton(
                    text=AdminRegistrationCodesMenuButtons.BACK, callback_data="admin_back_to_menu"
                )
            ],
        ]
    )


def get_registration_codes_list_keyboard(
    codes: list[dict],
    page: int,
    total_pages: int,
    filter_status: str = "all",  # all, active, used
) -> InlineKeyboardMarkup:
    """Клавиатура со списком кодов и пагинацией."""
    builder = InlineKeyboardBuilder()

    # Кнопки фильтров
    builder.row(
        InlineKeyboardButton(
            text=f"{'✅ ' if filter_status == 'active' else ''}Активные",
            callback_data="admin_codes_filter_active",
        ),
        InlineKeyboardButton(
            text=f"{'✅ ' if filter_status == 'used' else ''}Использованные",
            callback_data="admin_codes_filter_used",
        ),
        InlineKeyboardButton(
            text=f"{'✅ ' if filter_status == 'all' else ''}Все",
            callback_data="admin_codes_filter_all",
        ),
    )

    # Список кодов
    for code in codes:
        status_icon = "🔴" if code.get("is_used") else "🟢"
        role_name = "Курьер" if code.get("role") == "courier" else "Магазин"
        # Выравниваем роль пробелами, чтобы длина строки была одинаковой (имитация колонок)
        role_name = role_name.center(9)

        # Используем моноширинный шрифт для всего текста, чтобы выравнивание работало лучше
        # Код (8 симв) | Роль (9 симв) | Статус
        code_text = code.get("code").ljust(8)
        text = f"`{code_text} │ {role_name} │ {status_icon}`"
        builder.row(
            InlineKeyboardButton(text=text, callback_data=f"admin_code_select_{code.get('id')}")
        )

    # Пагинация
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="⬅️", callback_data=f"admin_codes_page_{page - 1}_{filter_status}"
            )
        )

    pagination_buttons.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop")
    )

    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="➡️", callback_data=f"admin_codes_page_{page + 1}_{filter_status}"
            )
        )

    builder.row(*pagination_buttons)

    # Кнопка назад
    builder.row(
        InlineKeyboardButton(
            text=AdminRegistrationCodesMenuButtons.BACK,
            callback_data="admin_back_to_registration_menu",
        )
    )

    return builder.as_markup()


def get_registration_code_details_keyboard(code_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Клавиатура детального просмотра кода."""
    builder = InlineKeyboardBuilder()

    if is_active:
        builder.row(
            InlineKeyboardButton(
                text="🚫 Деактивировать",
                callback_data=f"admin_code_deactivate_{code_id}",
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=AdminRegistrationCodesMenuButtons.BACK,
            callback_data="admin_view_codes",  # Возврат к списку
        )
    )

    return builder.as_markup()


def get_back_to_registration_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возврата в меню 'Код регистрации'"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AdminRegistrationCodesMenuButtons.BACK,
                    callback_data="admin_back_to_registration_menu",
                )
            ]
        ]
    )
