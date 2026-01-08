# keyboards.py — Кнопки входа/регистрации
# Этот файл реэкспортирует клавиатуры из bot/keyboards/auth.py (если есть)
# и может содержать локальные клавиатуры, специфичные только для auth handlers

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_register_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой регистрации для гостей."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Зарегистрироваться",
                    callback_data="start_registration",
                )
            ]
        ]
    )


def get_cancel_registration_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены регистрации."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить регистрацию",
                    callback_data="cancel_registration",
                )
            ]
        ]
    )
