"""Клавиатуры создания заказа."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from backend.src.common.enums import DeliveryTimeType, OrderType

from bot.handlers.shop.orders.callbacks import (
    CourierSelectionCallback,
    DeliveryTimeTypeCallback,
    OrderTypeCallback,
)


def get_order_settings_keyboard(
    order_type: str = OrderType.REGULAR.value,
    delivery_time_type: DeliveryTimeType = DeliveryTimeType.TODAY,
    price: int | None = None,
) -> InlineKeyboardMarkup:
    """Клавиатура настройки заказа после ввода описания."""
    keyboard = [
        [
            InlineKeyboardButton(text="◀️ Главное меню", callback_data="shop_main_menu"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="create_order"),
        ],
        [InlineKeyboardButton(text="📦 Тип заказа", callback_data="set_order_type")],
    ]

    # Кнопка времени для типа TIME
    if order_type == OrderType.TIME.value and delivery_time_type == DeliveryTimeType.SCHEDULED:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="⏰ Установить время доставки",
                    callback_data=DeliveryTimeTypeCallback(
                        time_type=delivery_time_type.value
                    ).pack(),
                )
            ]
        )

    # Кнопки цены
    if price is None:
        keyboard.append(
            [
                InlineKeyboardButton(text="💰 Установить цену", callback_data="set_order_price"),
                InlineKeyboardButton(text="⏩ Без цены", callback_data="skip_price"),
            ]
        )
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"💰 Изменить цену ({price:,} ₸)", callback_data="set_order_price"
                )
            ]
        )
        keyboard.append(
            [InlineKeyboardButton(text="✅ Далее к подтверждению", callback_data="skip_price")]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_order_type_keyboard(
    current_type: str | None = None, back_callback: str = "back_to_preview"
) -> InlineKeyboardMarkup:
    """Выбор типа заказа."""
    builder = InlineKeyboardBuilder()

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

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))

    return builder.as_markup()


def get_delivery_time_keyboard(
    current_time_type: str | None = None, back_callback: str = "back_to_preview"
) -> InlineKeyboardMarkup:
    """Выбор типа времени доставки."""
    builder = InlineKeyboardBuilder()

    time_types = {
        DeliveryTimeType.ASAP.value: ("🚀", "Как можно скорее"),
        DeliveryTimeType.SCHEDULED.value: ("⏰", "К конкретному времени"),
    }

    for time_val, (emoji, title) in time_types.items():
        text = f"{emoji} {title}"
        if current_time_type == time_val:
            text = f"✅ {text}"

        builder.button(text=text, callback_data=DeliveryTimeTypeCallback(time_type=time_val))

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))

    return builder.as_markup()


def get_price_input_keyboard(back_callback: str = "back_to_preview") -> InlineKeyboardMarkup:
    """Клавиатура этапа ввода цены."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏩ Пропустить (без цены)", callback_data="skip_price")],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback),
                InlineKeyboardButton(text="◀️ Главное меню", callback_data="shop_main_menu"),
            ],
        ]
    )


def get_time_input_keyboard(back_callback: str = "back_to_preview") -> InlineKeyboardMarkup:
    """Клавиатура ввода конкретного времени."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data=back_callback),
                InlineKeyboardButton(text="◀️ Главное меню", callback_data="shop_main_menu"),
            ]
        ]
    )


def get_courier_selection_keyboard(
    couriers: list[dict], page: int = 1, total: int = 0, limit: int = 5
) -> InlineKeyboardMarkup:
    """Выбор курьера с пагинацией."""
    builder = InlineKeyboardBuilder()
    total_pages = (total + limit - 1) // limit

    # Автовыбор
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
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop")
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

    builder.row(InlineKeyboardButton(text="🔙 Назад к цене", callback_data="set_order_price"))

    return builder.as_markup()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Финальное подтверждение заказа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="order_confirm"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="order_cancel"),
            ],
            [InlineKeyboardButton(text="🔙 Изменить заказ", callback_data="edit_order_menu")],
        ]
    )


def get_edit_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню редактирования заказа перед созданием."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить описание", callback_data="edit_order_description"
                )
            ],
            [InlineKeyboardButton(text="📦 Изменить тип заказа", callback_data="edit_order_type")],
            [InlineKeyboardButton(text="💰 Изменить цену", callback_data="edit_order_price")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_confirmation")],
        ]
    )
