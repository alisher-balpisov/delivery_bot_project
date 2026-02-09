from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from backend.src.common.enums import UserRole
from bot.handlers.admin.messages import AdminMainButtons, AdminRegistrationCodesMenuButtons
from bot.messages import AdminKeyboardMessages

# keyboards/admin.py


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.REGISTRATION_CODE,
                    callback_data="get_registration_code_menu",
                ),
                InlineKeyboardButton(text=AdminMainButtons.ORDERS, callback_data="show_orders"),
            ],
            [
                InlineKeyboardButton(text=AdminMainButtons.COURIERS, callback_data="show_couriers"),
                InlineKeyboardButton(text=AdminMainButtons.SHOPS, callback_data="show_shops"),
            ],
            [
                InlineKeyboardButton(text=AdminMainButtons.DISPUTES, callback_data="show_disputes"),
                InlineKeyboardButton(
                    text="📊 Экспорт статистики",
                    callback_data="show_statistics_admin",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📈 Системная статистика",
                    callback_data="show_system_stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=AdminMainButtons.EDIT_PROFILE, callback_data="get_edit_profile_menu"
                ),
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
        role_name = "Курьер" if code.get("role") == UserRole.COURIER else "Магазин"
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
        ),
        InlineKeyboardButton(
            text="Главное меню",
            callback_data="show_main_menu",
        ),
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
        ),
        InlineKeyboardButton(
            text="Главное меню",
            callback_data="show_main_menu",
        ),
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
                ),
                InlineKeyboardButton(
                    text="Главное меню",
                    callback_data="show_main_menu",
                ),
            ]
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


class StatsType(str, Enum):
    """Типы статистики для экспорта."""

    COMMON = "common"
    ADVANCED = "advanced"


class StatsCallback(CallbackData, prefix="stats"):
    """Callback data для работы со статистикой."""

    action: str  # menu, export_shop, export_courier, export_all, select_dates, download
    entity_type: str | None = None  # shop, courier, all
    entity_id: int | None = None
    stats_type: StatsType | None = None
    from_last_payment: bool = False
    page: int = 1


def get_statistics_main_menu() -> InlineKeyboardMarkup:
    """Главное меню статистики."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика магазина",
                    callback_data=StatsCallback(action="select_shop", entity_type="shop").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚴 Статистика курьера",
                    callback_data=StatsCallback(
                        action="select_courier", entity_type="courier"
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏪 Общая статистика магазинов",
                    callback_data=StatsCallback(action="export_all", entity_type="all").pack(),
                )
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back_to_menu")],
        ]
    )


def get_stats_type_keyboard(entity_type: str, entity_id: int | None = None) -> InlineKeyboardMarkup:
    """Выбор типа статистики (common/advanced)."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📋 Базовая",
            callback_data=StatsCallback(
                action="select_period",
                entity_type=entity_type,
                entity_id=entity_id,
                stats_type=StatsType.COMMON,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="📊 Расширенная",
            callback_data=StatsCallback(
                action="select_period",
                entity_type=entity_type,
                entity_id=entity_id,
                stats_type=StatsType.ADVANCED,
            ).pack(),
        ),
    )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=StatsCallback(action="menu").pack())
    )

    return builder.as_markup()


def get_period_selection_keyboard(
    entity_type: str, entity_id: int | None, stats_type: StatsType
) -> InlineKeyboardMarkup:
    """Выбор периода для статистики."""
    builder = InlineKeyboardBuilder()

    # Быстрые периоды
    builder.row(
        InlineKeyboardButton(
            text="📅 Сегодня",
            callback_data=StatsCallback(
                action="export_quick",
                entity_type=entity_type,
                entity_id=entity_id,
                stats_type=stats_type,
                page=0,  # 0 = today
            ).pack(),
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📅 Эта неделя",
            callback_data=StatsCallback(
                action="export_quick",
                entity_type=entity_type,
                entity_id=entity_id,
                stats_type=stats_type,
                page=7,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="📅 Этот месяц",
            callback_data=StatsCallback(
                action="export_quick",
                entity_type=entity_type,
                entity_id=entity_id,
                stats_type=stats_type,
                page=30,
            ).pack(),
        ),
    )

    # Специальная опция для магазинов/курьеров
    if entity_type in ("shop", "courier"):
        from_last_text = (
            "💰 С последней инкассации" if entity_type == "shop" else "💵 С последней выплаты"
        )
        builder.row(
            InlineKeyboardButton(
                text=from_last_text,
                callback_data=StatsCallback(
                    action="export_from_last",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    stats_type=stats_type,
                    from_last_payment=True,
                ).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=StatsCallback(
                action="select_type", entity_type=entity_type, entity_id=entity_id
            ).pack(),
        )
    )

    return builder.as_markup()


def get_export_loading_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для отображения во время экспорта."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Отмена", callback_data=StatsCallback(action="menu").pack()
                )
            ]
        ]
    )
