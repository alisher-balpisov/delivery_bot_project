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
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import DeliveryTimeType, OrderType, UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.couriers_client import CouriersClient
from bot.clients.orders_client import OrdersClient
from bot.clients.shops_client import ShopsClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards import (
    back_to_menu,
    format_order_confirmation_text,
    format_order_preview,
    get_courier_selection_keyboard,
    get_edit_order_menu_keyboard,
    get_order_confirmation_keyboard,
    get_order_settings_keyboard,
    get_price_input_keyboard,
    get_time_input_keyboard,
    set_order_time_keyboard,
    set_order_type_keyboard,
)
from bot.handlers.shop.messages import ShopOrder
from bot.handlers.shop.service import (
    CourierSelectionCallback,
    DeliveryTimeTypeCallback,
    OrderTypeCallback,
    create_order,
    get_order_type_requirements,
    validate_delivery_time,
    validate_price,
)
from bot.handlers.shop.states import OrderStates
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

router = Router(name="shop_create_orders_handlers")


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

    keyboard = back_to_menu()

    await callback.message.edit_text(ShopOrder.CREATE, reply_markup=keyboard, parse_mode="HTML")
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
    auth_client: AuthClient,
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

    # Устанавливаем дефолтный тип заказа и время доставки
    order_type = OrderType.REGULAR.value
    delivery_time_type = DeliveryTimeType.TODAY.value
    await state.update_data(
        order_type=order_type,
        delivery_time_type=delivery_time_type,
    )

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
        reply_markup=get_order_settings_keyboard(
            order_type=order_type,
            delivery_time_type=DeliveryTimeType.TODAY,
        ),
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

    await callback.message.edit_text(
        text=ShopOrder.TYPE,
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
    current_state = await state.get_state()
    is_editing = current_state == OrderStates.editing_type

    # Если выбран НЕ-TIME тип — сбрасываем время доставки
    if new_type != OrderType.TIME.value:
        await state.update_data(
            order_type=new_type,
            delivery_time_type=DeliveryTimeType.TODAY.value,
            delivery_time=None,
        )
    else:
        # Для TIME типа сохраняем только order_type
        await state.update_data(order_type=new_type)

    if callback_data.need_time:
        # Если выбираем время в режиме редактирования - кнопка назад ведёт в меню
        back_callback = "edit_order_menu" if is_editing else "back_to_preview"

        await callback.message.edit_text(
            "Выберите время заказа",
            reply_markup=set_order_time_keyboard(back_callback=back_callback),
        )
        return

    # Если мы в режиме редактирования и время не требуется — сразу готово
    if is_editing:
        await back_to_confirmation_handler(callback, state)
        return

    # ОБЫЧНЫЙ ФЛОУ СОЗДАНИЯ:
    # Получаем информацию о требованиях для этого типа
    requirements = get_order_type_requirements(new_type)

    # Показываем уведомление с информацией о типе
    await callback.answer(f"Тип изменён: {requirements['description'][:50]}...", show_alert=False)

    # Возвращаемся к предпросмотру заказа
    await back_to_order_preview(callback, state)


@router.callback_query(DeliveryTimeTypeCallback.filter(), RoleFilter(UserRole.SHOP))
async def save_delivery_time_type_handler(
    callback: CallbackQuery,
    callback_data: DeliveryTimeTypeCallback,
    state: FSMContext,
):
    """Обрабатывает выбор типа времени доставки"""
    new_time_type = callback_data.time_type
    current_state = await state.get_state()
    is_editing = current_state == OrderStates.editing_type

    # Сохраняем новый тип времени
    await state.update_data(delivery_time_type=new_time_type)

    back_callback = "edit_order_menu" if is_editing else "back_to_preview"

    # Если выбрано конкретное время - запрашиваем ввод
    if new_time_type == DeliveryTimeType.SCHEDULED.value:
        await callback.message.edit_text(
            text=ShopOrder.DELIVERY_TIME,
            reply_markup=get_time_input_keyboard(back_callback=back_callback),
            parse_mode="HTML",
        )
        await state.set_state(OrderStates.waiting_for_time)
        await callback.answer()
        return

    # Если мы в режиме редактирования и время не требуется — сразу готово
    if is_editing:
        await back_to_confirmation_handler(callback, state)
        return

    # Для других типов - обновляем клавиатуру и показываем уведомление (ОБЫЧНЫЙ ФЛОУ)
    await callback.message.edit_reply_markup(
        reply_markup=set_order_time_keyboard(
            current_time_type=new_time_type, back_callback=back_callback
        )
    )
    await callback.answer("Тип времени доставки изменён!")


@router.message(OrderStates.waiting_for_time, RoleFilter(UserRole.SHOP))
async def process_delivery_time_input(message: Message, state: FSMContext):
    """Обрабатывает ввод конкретного времени доставки"""
    time_text = message.text
    data = await state.get_data()
    is_editing = data.get("is_editing", False)
    back_callback = "edit_order_menu" if is_editing else "back_to_preview"

    if not time_text:
        await message.answer("⚠️ Пожалуйста, введите время в текстовом формате.", parse_mode="HTML")
        return

    # Валидируем время
    delivery_time, error = validate_delivery_time(time_text)

    if error:
        await message.answer(
            f"❌ {error}",
            reply_markup=get_time_input_keyboard(back_callback=back_callback),
            parse_mode="HTML",
        )
        return

    # Сохраняем время доставки
    await state.update_data(delivery_time=delivery_time)

    # Если мы в режиме редактирования - переходим к подтверждению
    if is_editing:
        await state.update_data(is_editing=False)  # Сбрасываем флаг

        # Этот код дублирует back_to_confirmation_handler, но нам нужно message.answer, а не callback.edit_text
        text = format_order_confirmation_text(
            shop_name=data.get("shop_name", "Магазин"),
            shop_address=data.get("shop_address", "Адрес"),
            description=data.get("description", ""),
            order_type=data.get("order_type", OrderType.REGULAR.value),
            price=float(data.get("price", 0)),
            delivery_time=delivery_time,
            delivery_time_type=data.get("delivery_time_type"),
        )

        await message.answer(
            f"✅ Время доставки обновлено!\n\n{text}",
            reply_markup=get_order_confirmation_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(OrderStates.confirmation)
        return

    # ОБЫЧНЫЙ ФЛОУ: Возвращаемся к предпросмотру заказа
    order_type = data.get("order_type", OrderType.TIME.value)

    text = format_order_preview(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
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
        ),
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
    delivery_time_type_str = data.get("delivery_time_type", DeliveryTimeType.TODAY.value)

    # Безопасное преобразование строки в enum
    try:
        delivery_time_type_enum = DeliveryTimeType(delivery_time_type_str)
    except ValueError:
        delivery_time_type_enum = DeliveryTimeType.TODAY

    text = format_order_preview(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
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
        ),
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
@router.message(OrderStates.editing_price, RoleFilter(UserRole.SHOP))
async def process_price_input(
    message: Message,
    state: FSMContext,
    couriers_client: CouriersClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Обрабатывает ввод цены и переходит к выбору курьера или подтверждению"""
    price_text = message.text
    data = await state.get_data()
    is_editing = data.get("is_editing", False)
    back_callback = "edit_order_menu" if is_editing else "back_to_preview"

    if not price_text:
        await message.answer("⚠️ Пожалуйста, введите цену числом.", parse_mode="HTML")
        return

    # Валидируем цену
    price, error = validate_price(price_text)

    if error:
        await message.answer(
            f"❌ {error}\n\n<i>Введите цену от 3 000 до 20 000 ₸</i>",
            reply_markup=get_price_input_keyboard(back_callback=back_callback),
            parse_mode="HTML",
        )
        return

    # Сохраняем цену
    await state.update_data(price=price, is_editing=False)
    data = await state.get_data()  # Обновляем данные

    # Если это редактирование цены - возвращаемся сразу к подтверждению (или меню редактирования)
    if is_editing:
        await _proceed_to_confirmation(message, state)
        return

    # Если REGULAR - пропускаем выбор курьера
    order_type = data.get("order_type", OrderType.REGULAR.value)
    if order_type == OrderType.REGULAR.value:
        await _proceed_to_confirmation(message, state)
        return

    # Для других типов - показываем выбор курьера
    telegram_id = message.from_user.id
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(telegram_id)

    if not token:
        await message.answer("⚠️ Ошибка авторизации. Попробуйте начать заново.")
        return

    # Запрашиваем активных курьеров (страница 1)
    await message.answer("⏳ Загружаем список курьеров...")
    result = await couriers_client.get_active_couriers_for_selection(token, page=1)

    if result.success and isinstance(result.data, dict) and result.data.get("items"):
        # Пагинированный ответ
        items = result.data["items"]
        total = result.data["total"]

        await message.answer(
            "🚚 <b>Выберите курьера</b>\n\n"
            "Вы можете выбрать конкретного курьера или доверить выбор системе.",
            reply_markup=get_courier_selection_keyboard(items, page=1, total=total),
            parse_mode="HTML",
        )
        await state.set_state(OrderStates.waiting_for_courier)
    elif result.success and isinstance(result.data, list) and len(result.data) > 0:
        # Fallback для старого формата (на всякий случай)
        await message.answer(
            "🚚 <b>Выберите курьера</b>\n\n"
            "Вы можете выбрать конкретного курьера или доверить выбор системе.",
            reply_markup=get_courier_selection_keyboard(result.data),
            parse_mode="HTML",
        )
        await state.set_state(OrderStates.waiting_for_courier)
    else:
        # Нет курьеров или ошибка - сообщаем и ставим автовыбор (None)
        msg = "⚠️ В данный момент нет свободных курьеров."
        if not result.success:
            msg = "⚠️ Не удалось загрузить список курьеров."

        await message.answer(
            f"{msg}\n"
            "Заказ будет создан в режиме ожидания курьера (система подберет первого освободившегося).",
            parse_mode="HTML",
        )
        # Устанавливаем курьера в None (авто/ожидание)
        await state.update_data(courier_id=None)
        await _proceed_to_confirmation(message, state)


@router.callback_query(
    CourierSelectionCallback.filter(F.courier_id == -1), RoleFilter(UserRole.SHOP)
)
async def pagination_courier_handler(
    callback: CallbackQuery,
    callback_data: CourierSelectionCallback,
    state: FSMContext,
    couriers_client: CouriersClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Обработка пагинации при выборе курьера"""
    page = callback_data.page
    telegram_id = callback.from_user.id
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(telegram_id)

    if not token:
        await callback.answer("⚠️ Ошибка авторизации", show_alert=True)
        return

    result = await couriers_client.get_active_couriers_for_selection(token, page=page)

    if result.success and isinstance(result.data, dict) and result.data.get("items"):
        items = result.data["items"]
        total = result.data["total"]

        await callback.message.edit_reply_markup(
            reply_markup=get_courier_selection_keyboard(items, page=page, total=total)
        )
    else:
        await callback.answer("⚠️ Не удалось загрузить страницу", show_alert=True)

    await callback.answer()


@router.callback_query(CourierSelectionCallback.filter(), RoleFilter(UserRole.SHOP))
async def select_courier_handler(
    callback: CallbackQuery,
    callback_data: CourierSelectionCallback,
    state: FSMContext,
    couriers_client: CouriersClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Обработка выбора курьера"""
    courier_id = callback_data.courier_id
    courier_name = None

    # 0 означает автовыбор — система подберёт курьера при создании заказа
    if courier_id == 0:
        await state.update_data(courier_id=None, courier_name=None)
        await callback.answer("Курьер будет подобран автоматически")
    else:
        # Получаем имя курьера для красивостей
        telegram_id = callback.from_user.id
        token_manager = TokenManager(auth_client, user_storage)
        token = await token_manager.get_token(telegram_id)

        if token:
            courier_info = await couriers_client.get_courier_details(token, courier_id)
            if courier_info.success and courier_info.data:
                courier_name = courier_info.data.get("full_name")

        await state.update_data(courier_id=courier_id, courier_name=courier_name)
        await callback.answer(f"Выбран курьер: {courier_name}")

    # Переходим к подтверждению.
    data = await state.get_data()
    text = format_order_confirmation_text(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=float(data.get("price", 0)),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_order_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderStates.confirmation)


async def _proceed_to_confirmation(message: Message, state: FSMContext):
    """Вспомогательная функция для перехода к подтверждению"""
    data = await state.get_data()

    text = format_order_confirmation_text(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=float(data.get("price", 0)),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )
    await message.answer(
        text=text,
        reply_markup=get_order_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderStates.confirmation)


# =============================================================================
# РЕДАКТИРОВАНИЕ ЗАКАЗА
# =============================================================================


@router.callback_query(F.data == "edit_order_menu", RoleFilter(UserRole.SHOP))
async def edit_order_menu_handler(callback: CallbackQuery, state: FSMContext):
    """
    Показывает меню редактирования заказа.
    """

    text = "<b>🔧 Редактирование заказа</b>\n\nВыберите, что хотите изменить:"

    await callback.message.edit_text(
        text=text,
        reply_markup=get_edit_order_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "edit_order_type", RoleFilter(UserRole.SHOP))
async def edit_order_type_handler(callback: CallbackQuery, state: FSMContext):
    """
    Запускает редактирование типа заказа.
    """
    data = await state.get_data()
    current_type = data.get("order_type", OrderType.REGULAR.value)

    await callback.message.edit_text(
        text=ShopOrder.TYPE,
        reply_markup=set_order_type_keyboard(
            current_type=current_type, back_callback="edit_order_menu"
        ),
        parse_mode="HTML",
    )
    await state.update_data(is_editing=True)
    await state.set_state(OrderStates.editing_type)
    await callback.answer()


@router.callback_query(F.data == "edit_order_price", RoleFilter(UserRole.SHOP))
async def edit_order_price_handler(callback: CallbackQuery, state: FSMContext):
    """
    Запускает редактирование цены заказа.
    """
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
    await state.set_state(OrderStates.editing_price)
    await callback.answer()


@router.callback_query(F.data == "back_to_confirmation", RoleFilter(UserRole.SHOP))
async def back_to_confirmation_handler(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает к экрану подтверждения заказа.
    """
    # Сбрасываем флаг редактирования
    await state.update_data(is_editing=False)
    data = await state.get_data()

    text = format_order_confirmation_text(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=float(data.get("price", 0)),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_order_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderStates.confirmation)
    await callback.answer()


@router.callback_query(F.data == "edit_order_description", RoleFilter(UserRole.SHOP))
async def edit_order_description_handler(callback: CallbackQuery, state: FSMContext):
    """
    Запускает редактирование описания заказа.
    Сохраняет все текущие данные заказа и переходит в режим ввода нового описания.
    """
    data = await state.get_data()
    current_description = data.get("description", "")

    text = (
        "<b>✏️ Изменение описания заказа</b>\n"
        f"<b>Текущее описание:</b>\n<blockquote>{current_description}</blockquote>\n\n"
        "<i>Введите новое описание заказа:</i>"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="cancel_edit_description",
                    )
                ]
            ]
        ),
        parse_mode="HTML",
    )
    await state.set_state(OrderStates.editing_description)
    await callback.answer()


@router.callback_query(F.data == "cancel_edit_description", RoleFilter(UserRole.SHOP))
async def cancel_edit_description_handler(callback: CallbackQuery, state: FSMContext):
    """
    Отменяет редактирование описания и возвращает к экрану подтверждения.
    """
    data = await state.get_data()

    # Возвращаемся к финальному подтверждению с текущими данными
    text = format_order_confirmation_text(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
        description=data.get("description", ""),
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=float(data.get("price", 0)),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_order_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderStates.confirmation)
    await callback.answer()


@router.message(OrderStates.editing_description, RoleFilter(UserRole.SHOP))
async def save_edited_description_handler(message: Message, state: FSMContext):
    """
    Сохраняет новое описание и возвращает к экрану подтверждения заказа.
    """
    new_description = message.text

    if not new_description:
        await message.answer(
            "⚠️ Пожалуйста, введите <b>текстовое</b> описание заказа.",
            parse_mode="HTML",
        )
        return

    # Сохраняем новое описание
    await state.update_data(description=new_description)

    # Получаем все данные заказа
    data = await state.get_data()

    # Показываем обновлённое подтверждение
    text = format_order_confirmation_text(
        shop_name=data.get("shop_name", "Магазин"),
        shop_address=data.get("shop_address", "Адрес"),
        description=new_description,
        order_type=data.get("order_type", OrderType.REGULAR.value),
        price=float(data.get("price", 0)),
        delivery_time=data.get("delivery_time"),
        delivery_time_type=data.get("delivery_time_type"),
        courier_name=data.get("courier_name"),
    )

    await message.answer(
        f"✅ <b>Описание обновлено!</b>\n\n{text}",
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
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Подтверждает и создаёт заказ через API"""
    data = await state.get_data()

    # Проверяем наличие всех обязательных данных
    if not data.get("description") or not data.get("price"):
        await callback.answer("⚠️ Недостаточно данных для создания заказа", show_alert=True)
        await create_order_handler(callback, state)
        return

    # Получаем токен через TokenManager (автоматический refresh)
    telegram_id = callback.from_user.id
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(telegram_id)

    if not token:
        await callback.answer("⚠️ Ошибка авторизации. Попробуйте перезайти.", show_alert=True)
        return

    # Показываем индикатор загрузки
    await callback.answer("⏳ Создаём заказ...")

    # Создаём заказ
    success, message = await create_order(
        token=token,
        order_details=data,
        orders_client=orders_client,
    )

    if success:
        await state.clear()
        await callback.message.edit_text(text=message, reply_markup=back_to_menu())
    else:
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
