from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from backend.src.common.enums import DeliveryTimeType, OrderType

from bot.handlers.shop.messages import ShopMainKeyboardsButtons, ShopOrder
from bot.handlers.shop.service import (
    CourierSelectionCallback,
    DeliveryTimeTypeCallback,
    OrderTypeCallback,
)


def get_shop_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню магазина"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.CREATE_ORDER,
                    callback_data="create_order",
                ),
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.CURRENT_ORDERS,
                    callback_data="show_current_orders",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.ORDER_HISTORY,
                    callback_data="show_order_history",
                ),
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.STATISTICS,
                    callback_data="show_statistics",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=ShopMainKeyboardsButtons.EDIT_PROFILE,
                    callback_data="edit_profile",
                )
            ],
        ]
    )


def back_to_menu() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой возврата в главное меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Главное меню",
                    callback_data="shop_main_menu",
                )
            ]
        ]
    )


def get_order_settings_keyboard(
    order_type: str = OrderType.REGULAR.value,
    delivery_time_type: DeliveryTimeType = DeliveryTimeType.TODAY,
) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру настройки заказа магазина.
    Показывается после ввода описания заказа.

    Args:
        order_type: Текущий тип заказа (значение enum)
        delivery_time_type: Текущий тип времени доставки
    """
    keyboard = [
        # Ряд 1: Навигация
        [
            InlineKeyboardButton(
                text="◀️ Главное меню",
                callback_data="shop_main_menu",
            ),
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="create_order",
            ),
        ],
        # Ряд 2: Установить тип заказа
        [
            InlineKeyboardButton(
                text="📦 Тип заказа",
                callback_data="set_order_type",
            )
        ],
    ]
    # Кнопка времени доставки появляется ТОЛЬКО если:
    if order_type == OrderType.TIME.value and delivery_time_type == DeliveryTimeType.SCHEDULED:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="⏰ Установить время доставки",
                    callback_data=(
                        DeliveryTimeTypeCallback(time_type=delivery_time_type.value).pack()
                    ),
                )
            ]
        )

    # Ряд 3: Далее (к установке цены)
    keyboard.append(
        [
            InlineKeyboardButton(
                text="💰 Далее (установить цену)",
                callback_data="set_order_price",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def set_order_type_keyboard(
    current_type: str | None = None, back_callback: str = "back_to_preview"
) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру выбора типа заказа с отметкой текущего.

    Args:
        current_type: Текущий выбранный тип (значение enum)
        back_callback: Callback data для кнопки "Назад"
    """
    builder = InlineKeyboardBuilder()

    # Словарь: Значение Enum -> Читаемое название с эмодзи
    order_types = {
        OrderType.REGULAR.value: ("🚴", "Обычный"),
        OrderType.TIME.value: ("⏰", "Ко времени"),
        OrderType.DISTANCE.value: ("🗺️", "Дальний"),
        OrderType.CUSTOM.value: ("📦", "Особый"),
        OrderType.SUPPLY.value: ("🏭", "Со склада"),
    }

    for type_val, (emoji, title) in order_types.items():
        text = f"{emoji} {title}"
        if current_type == type_val:
            text = f"✅ {text}"

        builder.button(
            text=text,
            callback_data=OrderTypeCallback(
                type=type_val, need_time=(type_val == OrderType.TIME.value)
            ),
        )

    builder.adjust(1)  # Кнопки в один столбец

    # Кнопка Назад
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))

    return builder.as_markup()


def set_order_time_keyboard(
    current_time_type: str | None = None, back_callback: str = "back_to_preview"
) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру выбора типа времени доставки.

    Args:
        current_time_type: Текущий выбранный тип времени (значение enum)
        back_callback: Callback data для кнопки "Назад"
    """
    builder = InlineKeyboardBuilder()

    # Типы времени доставки
    time_types = {
        DeliveryTimeType.ASAP.value: ("🚀", "Как можно скорее"),
        # DeliveryTimeType.TODAY.value: ("📅", "В течение дня"),
        DeliveryTimeType.SCHEDULED.value: ("⏰", "К конкретному времени"),
    }

    for time_val, (emoji, title) in time_types.items():
        text = f"{emoji} {title}"
        if current_time_type == time_val:
            text = f"✅ {text}"

        builder.button(text=text, callback_data=DeliveryTimeTypeCallback(time_type=time_val))

    builder.adjust(1)

    # Кнопка назад
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))

    return builder.as_markup()


def get_price_input_keyboard(back_callback: str = "back_to_preview") -> InlineKeyboardMarkup:
    """Клавиатура для этапа ввода цены (с кнопкой отмены)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=back_callback,
                ),
                InlineKeyboardButton(
                    text="◀️ Главное меню",
                    callback_data="shop_main_menu",
                ),
            ]
        ]
    )


def get_order_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура финального подтверждения заказа.
    Показывается после ввода цены.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить заказ",
                    callback_data="order_confirm",
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="order_cancel",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Изменить заказ",
                    callback_data="edit_order_menu",
                ),
            ],
        ]
    )


def get_edit_order_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура меню редактирования заказа.
    Показывает опции: изменить описание, тип заказа, цену.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить описание",
                    callback_data="edit_order_description",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📦 Изменить тип заказа",
                    callback_data="edit_order_type",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Изменить цену",
                    callback_data="edit_order_price",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="back_to_confirmation",
                ),
            ],
        ]
    )


def get_time_input_keyboard(back_callback: str = "back_to_preview") -> InlineKeyboardMarkup:
    """Клавиатура для этапа ввода конкретного времени доставки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад к настройкам",
                    callback_data=back_callback,
                ),
                InlineKeyboardButton(
                    text="◀️ Главное меню",
                    callback_data="shop_main_menu",
                ),
            ]
        ]
    )


def get_courier_selection_keyboard(
    couriers: list[dict], page: int = 1, total: int = 0, limit: int = 5
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора курьера с пагинацией.
    """
    builder = InlineKeyboardBuilder()
    total_pages = (total + limit - 1) // limit

    # Кнопка 'Автовыбор' — система сама подберёт курьера
    builder.row(
        InlineKeyboardButton(
            text="🔄 Автоматический подбор",
            callback_data=CourierSelectionCallback(courier_id=0).pack(),
        )
    )

    # Список курьеров
    for courier in couriers:
        rating_str = f"{courier['rating']:.1f}" if courier["rating"] else "N/A"
        name = courier["full_name"] or "Курьер"
        text = f"{name} (📦 {courier['active_orders_count']} | ⭐ {rating_str})"

        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=CourierSelectionCallback(courier_id=courier["id"]).pack(),
            )
        )

    # Пагинация
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=CourierSelectionCallback(courier_id=-1, page=page - 1).pack(),
            )
        )

    pagination_buttons.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="noop",  # Кнопка-информатор, ничего не делает
        )
    )

    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=CourierSelectionCallback(courier_id=-1, page=page + 1).pack(),
            )
        )

    if pagination_buttons:
        builder.row(*pagination_buttons)

    # Кнопка отмены/назад
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад к цене",
            callback_data="set_order_price",
        )
    )

    return builder.as_markup()


def format_order_preview(
    shop_name: str,
    shop_address: str,
    description: str,
    order_type: str,
    delivery_time: datetime | None = None,
    delivery_time_type: str | None = None,
    price: float | None = None,
) -> str:
    """
    Форматирует текст предпросмотра заказа.

    Args:
        shop_name: Название магазина
        shop_address: Адрес магазина
        description: Описание заказа
        order_type: Тип заказа
        delivery_time: Время доставки (для типа TIME)
        delivery_time_type: Тип времени доставки
        price: Цена заказа (если установлена)
    """
    # Преобразуем тип заказа в читаемый формат
    order_type_labels = {
        OrderType.REGULAR.value: "🚴 Обычный",
        OrderType.TIME.value: "⏰ Ко времени",
        OrderType.DISTANCE.value: "🗺️ Дальний",
        OrderType.CUSTOM.value: "📦 Особый",
        OrderType.SUPPLY.value: "🏭 Со склада",
    }
    order_type_display = order_type_labels.get(order_type, order_type)

    # Формируем текст
    text = ShopOrder.PREVIEW.format(
        shop_name=shop_name,
        shop_address=shop_address,
        description=description,
        order_type_display=order_type_display,
    )

    # Добавляем информацию о времени доставки для типа TIME
    if order_type == OrderType.TIME.value:
        time_type_labels = {
            DeliveryTimeType.ASAP.value: "🚀 Как можно скорее",
            DeliveryTimeType.TODAY.value: "📅 В течение дня",
            DeliveryTimeType.SCHEDULED.value: "⏰ К конкретному времени",
        }
        time_type_display = time_type_labels.get(delivery_time_type, "Не указано")
        text += f"⏱️ <b>Срочность:</b> {time_type_display}\n"

        if delivery_time and delivery_time_type == DeliveryTimeType.SCHEDULED.value:
            text += f"🕐 <b>Время:</b> {delivery_time.strftime('%d.%m.%Y %H:%M')}\n"

    # Добавляем цену если установлена
    if price is not None:
        text += f"\n💰 <b>Цена доставки:</b> {price:,.0f} ₸\n"

    text += "<i>Настройте параметры заказа используя кнопки ниже.</i>"

    return text


def format_order_confirmation_text(
    shop_name: str,
    shop_address: str,
    description: str,
    order_type: str,
    price: float,
    delivery_time: datetime | None = None,
    delivery_time_type: str | None = None,
    courier_name: str | None = None,
) -> str:
    """
    Форматирует финальный текст для подтверждения заказа.
    """
    order_type_labels = {
        OrderType.REGULAR.value: "🚴 Обычный",
        OrderType.TIME.value: "⏰ Ко времени",
        OrderType.DISTANCE.value: "🗺️ Дальний",
        OrderType.CUSTOM.value: "📦 Особый",
        OrderType.SUPPLY.value: "🏭 Со склада",
    }
    order_type_display = order_type_labels.get(order_type, order_type)

    text = (
        f"<b>✅ Подтверждение заказа</b>\n"
        f"🏢 <b>Магазин:</b> {shop_name}\n"
        f"📍 <b>Адрес:</b> {shop_address}\n\n"
        f"📝 <b>Описание:</b>\n{description}\n\n"
        f"📦 <b>Тип:</b> {order_type_display}\n"
        f"💰 <b>Цена:</b> {price:,.0f} ₸\n"
    )

    if order_type == OrderType.TIME.value and delivery_time:
        text += f"🕐 <b>Время доставки:</b> {delivery_time.strftime('%d.%m.%Y %H:%M')}\n"

    if courier_name:
        text += f"🚚 <b>Курьер:</b> {courier_name}\n"
    elif order_type != OrderType.REGULAR.value:
        text += "🚚 <b>Курьер:</b> Автоматический подбор\n"

    text += "\n\n<b>Подтвердите создание заказа</b>"

    return text
