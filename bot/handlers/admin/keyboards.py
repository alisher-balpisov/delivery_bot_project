# keyboards.py — Все клавиатуры админа
# Этот файл реэкспортирует клавиатуры из bot/keyboards/admin.py для удобства
# и может содержать локальные клавиатуры, специфичные только для admin handlers

from bot.keyboards.admin import (
    get_admin_main_keyboard,
    get_back_to_menu_keyboard,
    get_back_to_registration_menu_keyboard,
    get_registration_code_details_keyboard,
    get_registration_code_menu_keyboard,
    get_registration_codes_list_keyboard,
    get_role_selection_keyboard,
)

__all__ = [
    "get_admin_main_keyboard",
    "get_back_to_menu_keyboard",
    "get_back_to_registration_menu_keyboard",
    "get_registration_code_details_keyboard",
    "get_registration_code_menu_keyboard",
    "get_registration_codes_list_keyboard",
    "get_role_selection_keyboard",
]
