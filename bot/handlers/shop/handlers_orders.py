"""
Обработчики создания заказа для магазина.

Поток создания заказа согласно схеме:
1. Главное меню -> "Создать заказ"
2. Ввод описания заказа (waiting_for_description)
3. Предпросмотр заказа с настройками (тип заказа, время)
4. Ввод цены (waiting_for_price)
5. Подтверждение и создание заказа (confirmation)
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from backend.src.common.enums import DeliveryTimeType, OrderType, UserRole

from bot.clients.orders_client import OrdersClient
from bot.clients.shops_client import ShopsClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards import (
    back_to_menu,
    format_order_confirmation_text,
    format_order_preview,
    get_order_confirmation_keyboard,
    get_order_settings_keyboard,
    get_price_input_keyboard,
    get_time_input_keyboard,
    set_order_time_keyboard,
    set_order_type_keyboard,
)
from bot.handlers.shop.service import (
    DeliveryTimeTypeCallback,
    OrderTypeCallback,
    create_order,
    get_order_type_requirements,
    validate_delivery_time,
    validate_price,
)
from bot.handlers.shop.states import OrderStates
from bot.redis_storage import UserDataStorage

router = Router(name="shop_orders_handlers")


# =============================================================================
# ШАГП 1: Начало создания заказа
# =============================================================================


@router.callback_query(F.data == "create_order", RoleFilter(UserRole.SHOP))
async def create_order_handler(callback: CallbackQuery, state: FSMContext):
    """
    Начало процесса создания заказа.
    Очищает предыдущие данные и запрашивает описание заказа.
    """
    # Очищаем состояние для нового заказа
    await state.clear()
    ic()
    text = (
        "<b>📝 Создание нового заказа</b>\n"
        "{'─' * 25}\n\n"
        "Введите информацию о заказе:\n"
        "• Номер телефона получателя\n"
        "• Адрес доставки\n"
        "• Дополнительную информацию\n\n"
        "<i>Можете вставить сообщение от заказчика целиком.\n"
        "Детали заказа всегда можно дополнить или изменить.</i>"
    )
    keyboard = back_to_menu()

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(OrderStates.waiting_for_description)
    await callback.answer()


# =============================================================================
# ШАГ 2: Получение описания заказа
# =============================================================================


@router.message(OrderStates.waiting_for_description, RoleFilter(UserRole.SHOP))
async def get_description_handler(
    message: Message,
    state: FSMContext,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """
    Принимает описание заказа и показывает предпросмотр.
    """
    description = message.text

    # Проверяем что прислали текст
    if not description:
        await message.answer(
            "⚠️ Пожалуйста, введите <b>текстовое</b> описание заказа.", parse_mode="HTML"
        )
        return

    # Сохраняем описание
    await state.update_data(description=description)

    # Получаем информацию о магазине
    telegram_id = message.from_user.id
    token = await user_storage.get_access_token(telegram_id)

    # Получаем данные магазина (пробуем из кеша)
    shop_info = await user_storage.get_cached_profile(telegram_id)

    if shop_info:
        shop_name = shop_info.get("name", "Ваш магазин")
        shop_address = shop_info.get("address", "Адрес не указан")
    else:
        # Если нет в кеше, используем заглушки (в реальности нужно запросить API)
        shop_name = "Ваш магазин"
        shop_address = "Адрес не указан"

    # Сохраняем данные магазина в state
    await state.update_data(
        shop_name=shop_name,
        shop_address=shop_address,
    )

    # Устанавливаем дефолтный тип заказа
    order_type = OrderType.REGULAR.value
    await state.update_data(order_type=order_type)

    # Формируем текст предпросмотра
    text = format_order_preview(
        shop_name=shop_name,
        shop_address=shop_address,
        description=description,
        order_type=order_type,
    )

    # Отправляем предпросмотр
    await message.answer(
        text=text,
        reply_markup=get_order_settings_keyboard(order_type=order_type),
        parse_mode="HTML",
    )


# =============================================================================
# ШАГ 3: Настройка параметров заказа (тип, время)
# =============================================================================


@router.callback_query(F.data == "set_order_type", RoleFilter(UserRole.SHOP))
async def open_order_type_menu(callback: CallbackQuery, state: FSMContext):
    """Открывает меню выбора типа заказа"""
    data = await state.get_data()
    current_type = data.get("order_type", OrderType.REGULAR.value)

    text = (
        "<b>📦 Выбор типа заказа</b>\n"
        f"{'─' * 25}\n\n"
        "🚴 <b>Обычный</b> — стандартная доставка\n"
        "⏰ <b>Ко времени</b> — доставка к определённому времени\n"
        "🗺️ <b>Дальний</b> — доставка на большое расстояние\n"
        "📦 <b>Особый</b> — габаритный груз или особые условия\n"
        "🏭 <b>Со склада</b> — нужно забрать товар со склада\n\n"
        f"<i>Текущий выбор отмечен галочкой ✅</i>"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=set_order_type_keyboard(current_type=current_type),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(OrderTypeCallback.filter(), RoleFilter(UserRole.SHOP))
async def save_order_type_handler(
    callback: CallbackQuery, callback_data: OrderTypeCallback, state: FSMContext
):
    """Обрабатывает выбор типа заказа"""
    new_type = callback_data.type

    # Сохраняем новый тип в State
    await state.update_data(order_type=new_type)

    # Получаем информацию о требованиях для этого типа
    requirements = get_order_type_requirements(new_type)

    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=set_order_type_keyboard(current_type=new_type)
    )

    # Показываем уведомление с информацией о типе
    await callback.answer(f"Тип изменён: {requirements['description'][:50]}...", show_alert=False)


@router.callback_query(F.data == "set_order_time", RoleFilter(UserRole.SHOP))
async def open_order_time_menu(callback: CallbackQuery, state: FSMContext):
    """Открывает меню выбора типа времени доставки"""
    data = await state.get_data()
    current_time_type = data.get("delivery_time_type", DeliveryTimeType.TODAY.value)

    text = (
        "<b>⏰ Выбор типа времени доставки</b>\n"
        f"{'─' * 25}\n\n"
        "🚀 <b>Как можно скорее</b> — срочная доставка\n"
        "📅 <b>В течение дня</b> — до конца рабочего дня\n"
        "⏰ <b>К конкретному времени</b> — укажите точное время\n\n"
        "<i>Выберите подходящий вариант</i>"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=set_order_time_keyboard(current_time_type=current_time_type),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(DeliveryTimeTypeCallback.filter(), RoleFilter(UserRole.SHOP))
async def save_delivery_time_type_handler(
    callback: CallbackQuery,
    callback_data: DeliveryTimeTypeCallback,
    state: FSMContext,
):
    """Обрабатывает выбор типа времени доставки"""
    new_time_type = callback_data.time_type

    # Сохраняем новый тип времени
    await state.update_data(delivery_time_type=new_time_type)

    # Если выбрано конкретное время - запрашиваем ввод
    if new_time_type == DeliveryTimeType.SCHEDULED.value:
        text = (
            "<b>🕐 Укажите время доставки</b>\n"
            f"{'─' * 25}\n\n"
            "Введите время в одном из форматов:\n"
            "• <code>HH:MM</code> — сегодня (например: 14:30)\n"
            "• <code>ДД.ММ HH:MM</code> — дата и время (например: 25.01 15:00)\n"
            "• <code>ДД.ММ.ГГГГ HH:MM</code> — полная дата (например: 25.01.2026 15:00)\n"
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_time_input_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(OrderStates.waiting_for_time)
        await callback.answer()
        return

    # Для других типов - обновляем клавиатуру и показываем уведомление
    await callback.message.edit_reply_markup(
        reply_markup=set_order_time_keyboard(current_time_type=new_time_type)
    )
    await callback.answer("Тип времени доставки изменён!")


@router.message(OrderStates.waiting_for_time, RoleFilter(UserRole.SHOP))
async def process_delivery_time_input(message: Message, state: FSMContext):
    """Обрабатывает ввод конкретного времени доставки"""
    time_text = message.text

    if not time_text:
        await message.answer("⚠️ Пожалуйста, введите время в текстовом формате.", parse_mode="HTML")
        return

    # Валидируем время
    delivery_time, error = validate_delivery_time(time_text)

    if error:
        await message.answer(
            f"❌ {error}",
            reply_markup=get_time_input_keyboard(),
            parse_mode="HTML",
        )
        return

    # Сохраняем время доставки
    await state.update_data(delivery_time=delivery_time)

    # Возвращаемся к предпросмотру заказа
    data = await state.get_data()

    text = format_order_preview(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        delivery_time=delivery_time,
        delivery_time_type=DeliveryTimeType.SCHEDULED.value,
    )

    await message.answer(
        f"✅ Время доставки установлено: {delivery_time.strftime('%d.%m.%Y %H:%M')}\n\n{text}",
        reply_markup=get_order_settings_keyboard(order_type=data.get("order_type")),
        parse_mode="HTML",
    )

    # Сбрасываем состояние (выходим из ожидания времени)
    await state.set_state(None)


@router.callback_query(F.data == "back_to_preview", RoleFilter(UserRole.SHOP))
async def back_to_order_preview(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к предпросмотру заказа"""
    data = await state.get_data()

    description = data.get("description")
    if not description:
        # Если нет описания - начинаем заново
        await create_order_handler(callback, state)
        return

    order_type = data.get("order_type", OrderType.REGULAR.value)

    text = format_order_preview(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
        description=description,
        order_type=order_type,
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        price=data.get("price"),
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_order_settings_keyboard(order_type=order_type),
        parse_mode="HTML",
    )

    # Сбрасываем состояние если были на вводе
    await state.set_state(None)
    await callback.answer()


# =============================================================================
# ШАГ 4: Установка цены
# =============================================================================


@router.callback_query(F.data == "set_order_price", RoleFilter(UserRole.SHOP))
async def request_order_price(callback: CallbackQuery, state: FSMContext):
    """Запрашивает цену заказа"""
    data = await state.get_data()

    # Проверяем, что есть описание
    if not data.get("description"):
        await callback.answer("⚠️ Сначала введите описание заказа", show_alert=True)
        await create_order_handler(callback, state)
        return

    # Проверяем требования для типа заказа TIME
    order_type = data.get("order_type")
    if order_type == OrderType.TIME.value:
        delivery_time_type = data.get("delivery_time_type")
        if delivery_time_type == DeliveryTimeType.SCHEDULED.value and not data.get("delivery_time"):
            await callback.answer(
                "⚠️ Для заказа 'Ко времени' нужно указать время доставки", show_alert=True
            )
            return

    text = (
        "<b>💰 Установка цены доставки</b>\n"
        f"{'─' * 25}\n\n"
        "Введите цену доставки в тенге.\n\n"
        "📋 <b>Ограничения:</b>\n"
        "• Минимальная цена: <b>3 000 ₸</b>\n"
        "• Максимальная цена: <b>20 000 ₸</b>\n\n"
        "<i>Введите только число (например: 5000)</i>"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_price_input_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderStates.waiting_for_price)
    await callback.answer()


@router.message(OrderStates.waiting_for_price, RoleFilter(UserRole.SHOP))
async def process_price_input(
    message: Message,
    state: FSMContext,
):
    """Обрабатывает ввод цены и показывает подтверждение"""
    price_text = message.text

    if not price_text:
        await message.answer("⚠️ Пожалуйста, введите цену числом.", parse_mode="HTML")
        return

    # Валидируем цену
    price, error = validate_price(price_text)

    if error:
        await message.answer(
            f"❌ {error}\n\n<i>Введите цену от 3 000 до 20 000 ₸</i>",
            reply_markup=get_price_input_keyboard(),
            parse_mode="HTML",
        )
        return

    # Сохраняем цену
    await state.update_data(price=price)

    # Показываем финальное подтверждение
    data = await state.get_data()

    text = format_order_confirmation_text(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=float(price),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
    )
    await message.answer(
        text=text,
        reply_markup=get_order_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderStates.confirmation)


# =============================================================================
# ШАГ 5: Подтверждение и создание заказа
# =============================================================================


@router.callback_query(F.data == "order_confirm", RoleFilter(UserRole.SHOP))
async def confirm_and_create_order(
    callback: CallbackQuery,
    state: FSMContext,
    orders_client: OrdersClient,
    user_storage: UserDataStorage,
):
    """Подтверждает и создаёт заказ через API"""
    print("jkewiowejweiodewijodewjidewji")
    data = await state.get_data()

    # Проверяем наличие всех обязательных данных
    if not data.get("description") or not data.get("price"):
        await callback.answer("⚠️ Недостаточно данных для создания заказа", show_alert=True)
        await create_order_handler(callback, state)
        return

    # Получаем токен
    telegram_id = callback.from_user.id
    token = await user_storage.get_access_token(telegram_id)

    if not token:
        await callback.answer("⚠️ Ошибка авторизации. Попробуйте перезайти.", show_alert=True)
        return

    # Показываем индикатор загрузки
    await callback.answer("⏳ Создаём заказ...")

    # Создаём заказ
    success, message, order_id = await create_order(
        token=token,
        order_details=data,
        orders_client=orders_client,
    )

    if success:
        # Очищаем состояние
        await state.clear()

        success_text = (
            f"<b>✅ Заказ успешно создан!</b>\n"
            f"{'═' * 25}\n\n"
            f"🆔 <b>Номер заказа:</b> #{order_id}\n"
            f"📦 <b>Статус:</b> Ожидает назначения курьера\n\n"
            f"<i>Вы получите уведомление, когда курьер примет заказ.</i>"
        )

        await callback.message.edit_text(
            text=success_text,
            reply_markup=back_to_menu(),
            parse_mode="HTML",
        )
    else:
        # Показываем ошибку, но не очищаем данные
        await callback.message.edit_text(
            text=f"❌ <b>Ошибка создания заказа</b>\n\n{message}",
            reply_markup=get_order_confirmation_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "order_cancel", RoleFilter(UserRole.SHOP))
async def cancel_order_creation(callback: CallbackQuery, state: FSMContext):
    """Отменяет создание заказа"""
    await state.clear()

    await callback.message.edit_text(
        text="❌ <b>Создание заказа отменено</b>\n\n<i>Вы можете создать новый заказ в любое время.</i>",
        reply_markup=back_to_menu(),
        parse_mode="HTML",
    )
    await callback.answer("Заказ отменён")
