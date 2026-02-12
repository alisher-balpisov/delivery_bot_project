"""Обработчики настройки типа и времени заказа."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import DeliveryTimeType, OrderType, UserRole

from bot.filters.filters import RoleFilter
from bot.handlers.shop.formatters.order import format_order_confirmation, format_order_preview
from bot.handlers.shop.keyboards.create_order import (
    get_confirmation_keyboard,
    get_delivery_time_keyboard,
    get_order_settings_keyboard,
    get_order_type_keyboard,
    get_time_input_keyboard,
)
from bot.handlers.shop.messages import OrderCreateMessages
from bot.handlers.shop.orders.callbacks import DeliveryTimeTypeCallback, OrderTypeCallback
from bot.handlers.shop.services.order_service import OrderCreationService
from bot.handlers.shop.states import OrderCreateStates
from bot.handlers.shop.validators.time import validate_delivery_time

router = Router(name="order_create_settings")


@router.callback_query(F.data == "set_order_type", RoleFilter(UserRole.SHOP))
async def open_order_type_menu(callback: CallbackQuery, state: FSMContext):
    """Открыть меню выбора типа заказа."""
    data = await state.get_data()
    current_type = data.get("order_type", OrderType.REGULAR.value)

    await callback.message.edit_text(
        text=OrderCreateMessages.TYPE_SELECTION,
        reply_markup=get_order_type_keyboard(current_type=current_type),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(OrderTypeCallback.filter(), RoleFilter(UserRole.SHOP))
async def save_order_type(
    callback: CallbackQuery, callback_data: OrderTypeCallback, state: FSMContext
):
    """Сохранить выбранный тип заказа."""
    new_type = callback_data.type
    current_state = await state.get_state()
    is_editing = current_state == OrderCreateStates.editing_type

    # Для не-TIME типов сбрасываем время
    if new_type != OrderType.TIME.value:
        await state.update_data(
            order_type=new_type,
            delivery_time_type=DeliveryTimeType.TODAY.value,
            delivery_time=None,
        )
    else:
        await state.update_data(order_type=new_type)

    # Если нужно выбрать время
    if callback_data.need_time:
        back_callback = "edit_order_menu" if is_editing else "back_to_preview"

        await callback.message.edit_text(
            "Выберите время заказа",
            reply_markup=get_delivery_time_keyboard(back_callback=back_callback),
        )
        return

    # Если в режиме редактирования - возврат к подтверждению
    if is_editing:
        await _back_to_confirmation(callback, state)
        return

    # Обычный флоу - показываем уведомление и возвращаемся к предпросмотру
    requirements = OrderCreationService.get_order_type_requirements(new_type)
    await callback.answer(f"Тип изменён: {requirements['description'][:50]}...", show_alert=False)
    await _back_to_preview(callback, state)


@router.callback_query(DeliveryTimeTypeCallback.filter(), RoleFilter(UserRole.SHOP))
async def save_delivery_time_type(
    callback: CallbackQuery,
    callback_data: DeliveryTimeTypeCallback,
    state: FSMContext,
):
    """Сохранить тип времени доставки."""
    new_time_type = callback_data.time_type
    current_state = await state.get_state()
    is_editing = current_state == OrderCreateStates.editing_type

    await state.update_data(delivery_time_type=new_time_type)

    back_callback = "edit_order_menu" if is_editing else "back_to_preview"

    # Если конкретное время - запрашиваем ввод
    if new_time_type == DeliveryTimeType.SCHEDULED.value:
        await callback.message.edit_text(
            text=OrderCreateMessages.TIME_PROMPT,
            reply_markup=get_time_input_keyboard(back_callback=back_callback),
            parse_mode="HTML",
        )
        await state.set_state(OrderCreateStates.waiting_for_time)
        await callback.answer()
        return

    # В режиме редактирования - возврат к подтверждению
    if is_editing:
        await _back_to_confirmation(callback, state)
        return

    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=get_delivery_time_keyboard(
            current_time_type=new_time_type, back_callback=back_callback
        )
    )
    await callback.answer("Тип времени доставки изменён!")


@router.message(OrderCreateStates.waiting_for_time, RoleFilter(UserRole.SHOP))
async def process_delivery_time_input(message: Message, state: FSMContext):
    """Обработать ввод конкретного времени."""
    time_text = message.text
    data = await state.get_data()
    is_editing = data.get("is_editing", False)
    back_callback = "edit_order_menu" if is_editing else "back_to_preview"

    if not time_text:
        await message.answer("⚠️ Пожалуйста, введите время в текстовом формате.", parse_mode="HTML")
        return

    # Валидация
    delivery_time, error = validate_delivery_time(time_text)

    if error:
        await message.answer(
            f"❌ {error}",
            reply_markup=get_time_input_keyboard(back_callback=back_callback),
            parse_mode="HTML",
        )
        return

    # Сохраняем время
    await state.update_data(delivery_time=delivery_time)

    # В режиме редактирования - показываем подтверждение
    if is_editing:
        await state.update_data(is_editing=False)

        text = format_order_confirmation(
            description=data.get("description", ""),
            order_type=data.get("order_type", OrderType.REGULAR.value),
            price=data.get("price"),
            delivery_time=delivery_time,
            delivery_time_type=data.get("delivery_time_type"),
        )

        await message.answer(
            f"✅ Время доставки обновлено!\n\n{text}",
            reply_markup=get_confirmation_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(OrderCreateStates.confirmation)
        return

    # Обычный флоу - возврат к предпросмотру
    order_type = data.get("order_type", OrderType.TIME.value)

    text = format_order_preview(
        description=data.get("description", ""),
        order_type=order_type,
        delivery_time=delivery_time,
        delivery_time_type=DeliveryTimeType.SCHEDULED.value,
    )

    await message.answer(
        f"✅ Время доставки установлено: {delivery_time.strftime('%d.%m.%Y %H:%M')}\n\n{text}",
        reply_markup=get_order_settings_keyboard(
            order_type=order_type,
            delivery_time_type=DeliveryTimeType.SCHEDULED,
            price=data.get("price"),
        ),
        parse_mode="HTML",
    )

    await state.set_state(None)


@router.callback_query(F.data == "back_to_preview", RoleFilter(UserRole.SHOP))
async def _back_to_preview(callback: CallbackQuery, state: FSMContext):
    """Возврат к предпросмотру заказа."""
    data = await state.get_data()

    description = data.get("description")
    if not description:
        from bot.handlers.shop.orders.create.description import start_order_creation

        await start_order_creation(callback, state)
        return

    order_type = data.get("order_type", OrderType.REGULAR.value)
    delivery_time_type_str = data.get("delivery_time_type", DeliveryTimeType.TODAY.value)

    try:
        delivery_time_type_enum = DeliveryTimeType(delivery_time_type_str)
    except ValueError:
        delivery_time_type_enum = DeliveryTimeType.TODAY

    text = format_order_preview(
        description=description,
        order_type=order_type,
        delivery_time=data.get("delivery_time"),
        delivery_time_type=delivery_time_type_str,
        price=data.get("price"),
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_order_settings_keyboard(
            order_type=order_type,
            delivery_time_type=delivery_time_type_enum,
            price=data.get("price"),
        ),
        parse_mode="HTML",
    )

    await state.set_state(None)
    await callback.answer()


async def _back_to_confirmation(callback: CallbackQuery, state: FSMContext):
    """Возврат к экрану подтверждения."""
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
