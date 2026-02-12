"""Обработчики редактирования заказа перед созданием."""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import OrderType, UserRole

from bot.filters.filters import RoleFilter
from bot.handlers.shop.formatters.order import format_order_confirmation
from bot.handlers.shop.keyboards.create_order import (
    get_confirmation_keyboard,
    get_edit_menu_keyboard,
    get_order_type_keyboard,
    get_price_input_keyboard,
)
from bot.handlers.shop.messages import OrderCreateMessages
from bot.handlers.shop.states import OrderCreateStates

router = Router(name="order_create_edit")


@router.callback_query(F.data == "edit_order_menu", RoleFilter(UserRole.SHOP))
async def edit_order_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Показать меню редактирования заказа."""
    text = "<b>🔧 Редактирование заказа</b>\n\nВыберите, что хотите изменить:"

    await callback.message.edit_text(
        text=text,
        reply_markup=get_edit_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "edit_order_type", RoleFilter(UserRole.SHOP))
async def edit_order_type_handler(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование типа заказа."""
    data = await state.get_data()
    current_type = data.get("order_type", OrderType.REGULAR.value)

    await callback.message.edit_text(
        text=OrderCreateMessages.TYPE_SELECTION,
        reply_markup=get_order_type_keyboard(
            current_type=current_type, back_callback="edit_order_menu"
        ),
        parse_mode="HTML",
    )
    await state.update_data(is_editing=True)
    await state.set_state(OrderCreateStates.editing_type)
    await callback.answer()


@router.callback_query(F.data == "edit_order_price", RoleFilter(UserRole.SHOP))
async def edit_order_price_handler(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование цены заказа."""
    text = (
        "<b>💰 Установка цены доставки</b>\n"
        "Введите новую цену доставки в тенге.\n\n"
        "<i>Введите только число (например: 5000)</i>"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_price_input_keyboard(back_callback="edit_order_menu"),
        parse_mode="HTML",
    )
    await state.update_data(is_editing=True)
    await state.set_state(OrderCreateStates.editing_price)
    await callback.answer()


@router.callback_query(F.data == "edit_order_description", RoleFilter(UserRole.SHOP))
async def edit_order_description_handler(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование описания заказа."""
    data = await state.get_data()
    current_description = data.get("description", "")

    text = (
        "<b>✏️ Изменение описания заказа</b>\n"
        f"<b>Текущее описание:</b>\n<blockquote>{html.escape(current_description)}</blockquote>\n\n"
        "<i>Введите новое описание заказа:</i>"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_description")]
            ]
        ),
        parse_mode="HTML",
    )
    await state.set_state(OrderCreateStates.editing_description)
    await callback.answer()


@router.callback_query(F.data == "cancel_edit_description", RoleFilter(UserRole.SHOP))
async def cancel_edit_description_handler(callback: CallbackQuery, state: FSMContext):
    """Отменить редактирование описания."""
    data = await state.get_data()

    text = format_order_confirmation(
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=data.get("price"),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderCreateStates.confirmation)
    await callback.answer()


@router.message(OrderCreateStates.editing_description, RoleFilter(UserRole.SHOP))
async def save_edited_description_handler(message: Message, state: FSMContext):
    """Сохранить новое описание."""
    new_description = message.text

    if not new_description:
        await message.answer(
            "⚠️ Пожалуйста, введите <b>текстовое</b> описание заказа.",
            parse_mode="HTML",
        )
        return

    # Сохраняем новое описание
    await state.update_data(description=new_description)
    data = await state.get_data()

    # Показываем обновлённое подтверждение
    text = format_order_confirmation(
        description=new_description,
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=data.get("price"),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await message.answer(
        f"✅ <b>Описание обновлено!</b>\n\n{text}",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderCreateStates.confirmation)


@router.callback_query(F.data == "back_to_confirmation", RoleFilter(UserRole.SHOP))
async def back_to_confirmation_handler(callback: CallbackQuery, state: FSMContext):
    """Возврат к экрану подтверждения заказа."""
    await state.update_data(is_editing=False)
    data = await state.get_data()

    text = format_order_confirmation(
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=data.get("price"),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderCreateStates.confirmation)
    await callback.answer()
