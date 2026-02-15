"""Клавиатуры для деталей заказа."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from backend.src.common.enums import OrderStatus

from bot.handlers.shop.orders.callbacks import OrderActionCallback


def get_shop_order_details_keyboard(
    order_id: int,
    status: str,
    back_callback: str,
    page: int,
    orders_status: str,
    courier_id: int | None = None,
    dispute_id: int | None = None,
    dispute_status: str | None = None,
    has_price: bool = True,
) -> InlineKeyboardMarkup:
    """Клавиатура деталей заказа с динамическими кнопками."""
    builder = InlineKeyboardBuilder()

    # 1. Посмотреть курьера
    if courier_id:
        builder.button(
            text="👤 Посмотреть курьера",
            callback_data=OrderActionCallback(order_id=order_id, action="view_courier").pack(),
        )

    # 2. Споры
    # Если есть активный спор - показываем "Посмотреть спор"
    if dispute_id and dispute_status in DisputeStatus.active_statuses():
        builder.button(
            text="⚖️ Посмотреть спор",
            callback_data=OrderActionCallback(
                order_id=order_id, action="view_dispute", page=page, status=orders_status
            ).pack(),
        )
    # Если спора нет ИЛИ последний спор завершен/отменен - показываем "Открыть спор"
    elif courier_id and status in OrderStatus.allowed_statuses_for_create_dispute():
        if not dispute_id or dispute_status in DisputeStatus.completed_statuses():
            builder.button(
                text="⚖️ Открыть спор",
                callback_data=OrderActionCallback(
                    order_id=order_id, action="open_dispute", page=page, status=orders_status
                ).pack(),
            )
        # Если есть завершенный спор, также даем возможность посмотреть историю (опционально,
        # но в данном случае dispute_id будет указывать на последний, так что "Посмотреть спор"
        # может работать как "Посмотреть последний спор")
        if dispute_id and dispute_status in DisputeStatus.completed_statuses():
            builder.button(
                text="⚖️ Посмотреть спор",
                callback_data=OrderActionCallback(
                    order_id=order_id, action="view_dispute", page=page, status=orders_status
                ).pack(),
            )

    # 3. Редактировать
    if status not in [OrderStatus.COMPLETED.value, OrderStatus.CANCELED.value]:
        builder.button(
            text="✏️ Редактировать",
            callback_data=OrderActionCallback(order_id=order_id, action="edit").pack(),
        )

    # 4. Добавить заметку
    builder.button(
        text="📝 Добавить заметку",
        callback_data=OrderActionCallback(order_id=order_id, action="add_note").pack(),
    )

    # 5. Завершить
    if status == OrderStatus.AWAITING_CONFIRMATION.value and has_price:
        builder.button(
            text="✅ Завершить заказ",
            callback_data=OrderActionCallback(order_id=order_id, action="complete").pack(),
        )

    # 6. Установить цену
    if not has_price and status not in [OrderStatus.COMPLETED.value, OrderStatus.CANCELED.value]:
        builder.button(
            text="💰 Установить цену",
            callback_data=OrderActionCallback(order_id=order_id, action="set_price").pack(),
        )

    # 7. Отменить
    if status in [OrderStatus.PENDING.value, OrderStatus.PENDING_COURIER.value]:
        builder.button(
            text="❌ Отменить заказ",
            callback_data=OrderActionCallback(order_id=order_id, action="cancel").pack(),
        )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))

    return builder.as_markup()


def get_shop_edit_menu_keyboard(
    order_id: int,
    back_callback: str,
    can_edit_price: bool = True,
    can_edit_description: bool = True,
    can_edit_courier: bool = False,
) -> InlineKeyboardMarkup:
    """Меню редактирования заказа."""
    builder = InlineKeyboardBuilder()

    if can_edit_price:
        builder.button(
            text="💰 Изменить цену",
            callback_data=OrderActionCallback(order_id=order_id, action="set_price").pack(),
        )

    if can_edit_description:
        builder.button(
            text="📝 Изменить описание",
            callback_data=OrderActionCallback(
                order_id=order_id, action="edit_order_description"
            ).pack(),
        )

    if can_edit_courier:
        builder.button(
            text="👤 Изменить курьера",
            callback_data=OrderActionCallback(order_id=order_id, action="change_courier").pack(),
        )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))

    return builder.as_markup()
