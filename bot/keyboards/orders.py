from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from backend.src.common.enums import OrderStatus
from bot.constants import ORDER_STATUS_EMOJIS
from bot.utils.formatters import format_dt_short


def get_orders_list_keyboard(
    orders: list[dict],
    page: int,
    total_pages: int,
    back_callback_data: str,
    callback_factory: Callable[[str, int, int | None], str],
    filter_status: str | None = None,
    filter_callback_factory: Callable[[str], str] | None = None,
) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры со списком заказов.

    Args:
        orders: Список заказов (dict)
        page: Текущая страница
        total_pages: Всего страниц
        back_callback_data: Callback data для кнопки "Назад"
        callback_factory: Функция для создания callback data (action, page, order_id)
        filter_status: Текущий фильтр (опционально)
        filter_callback_factory: Функция для создания callback data фильтров (status) (опционально)
    """
    builder = InlineKeyboardBuilder()

    # Кнопки фильтров (если передана фабрика)
    if filter_callback_factory:
        is_active = filter_status == "active"
        is_completed = filter_status == "completed"
        is_all = filter_status is None or filter_status == "all"

        builder.row(
            InlineKeyboardButton(
                text=f"{'✅ ' if is_active else ''}Активные",
                callback_data=filter_callback_factory("active"),
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if is_completed else ''}Заверш.",
                callback_data=filter_callback_factory("completed"),
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if is_all else ''}Все",
                callback_data=filter_callback_factory("all"),
            ),
        )

    # Список заказов
    for order in orders:
        order_id = order.get("id")
        status = order.get("status", "unknown")
        address = order.get("recipient_address", "Нет адреса")

        # Форматируем дату
        date = format_dt_short(order.get("created_at", ""))

        # Эмодзи статусов

        # Пробуем получить по Enum, если нет - по строке, иначе первая буква
        # Если status - это строка, пробуем преобразовать в Enum
        try:
            status_enum = OrderStatus(status)
            status_icon = ORDER_STATUS_EMOJIS.get(status_enum, status[:1].upper())
        except ValueError:
            # Если не Enum, проверяем напрямую в словаре или берем первую букву
            status_icon = ORDER_STATUS_EMOJIS.get(status, status[:1].upper())

        # Умное сокращение адреса
        max_address_len = 20
        if len(address) > max_address_len:
            address = address[: max_address_len - 3] + "..."

        # Формируем текст кнопки
        # Если есть цена (для админов/магазинов может быть важно), можно добавить
        # Но для курьеров важнее адрес.
        # Давайте сделаем универсально: #ID | Status | Address | Date

        button_text = f"#{order_id} | {status_icon} | {address} | {date}"

        # Для админов может быть другой формат, но пока оставим так.
        # Если нужно, можно передавать formatter в функцию.

        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=callback_factory("order_detail", page, order_id),
            )
        )

    # Пагинация
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=callback_factory("history", page - 1, None),
            )
        )

    pagination_buttons.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=callback_factory("history", page + 1, None),
            )
        )

    builder.row(*pagination_buttons)

    # Кнопка Назад
    builder.row(
        InlineKeyboardButton(
            text="Назад",
            callback_data=back_callback_data,
        ),
    )

    return builder.as_markup()


def get_order_details_keyboard(
    back_callback_data: str,
    order_status: str | None = None,
    cancel_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры для детального просмотра заказа.

    Args:
        back_callback_data: Callback data для кнопки "Назад" (возврат к списку)
        order_status: Статус заказа (для определения доступных действий)
        cancel_callback_data: Callback data для кнопки отмены (если доступна)
    """
    builder = InlineKeyboardBuilder()

    # Действия с заказом (например, отмена для админа)
    if cancel_callback_data and order_status in [
        "NEW",
        "SEARCHING",
        "COURIER_ASSIGNED",
        "COURIER_EN_ROUTE",
        "DELIVERING",
        "ACTIVE",
    ]:
        builder.row(
            InlineKeyboardButton(
                text="❌ Отменить заказ",
                callback_data=cancel_callback_data,
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="Назад",
            callback_data=back_callback_data,
        ),
        InlineKeyboardButton(
            text="Главное меню",
            callback_data="show_main_menu",
        ),
    )

    return builder.as_markup()
