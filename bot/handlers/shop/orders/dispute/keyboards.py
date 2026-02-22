"""Клавиатуры для споров."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.handlers.shop.orders.callbacks import (
    DisputeReasonCallback,
    DisputesListCallback,
    OrderActionCallback,
    OrderDetailCallback,
    OrderRefundCallback,
)


def get_pre_dispute_keyboard(
    order_id: int, page: int = 1, status: str = "all"
) -> InlineKeyboardMarkup:
    """Клавиатура перед открытием спора (контакты)."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Далее ➡️",
        callback_data=OrderActionCallback(
            order_id=order_id, action="dispute_next", page=page, status=status
        ).pack(),
    )
    # Кнопка назад возвращает в карточку заказа
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=OrderDetailCallback(
                order_id=order_id, from_page=page, from_status=status
            ).pack(),
        )
    )
    return builder.as_markup()


def get_dispute_reason_keyboard(
    order_id: int, page: int = 1, status: str = "all"
) -> InlineKeyboardMarkup:
    """Клавиатура с причинами спора (Inline)."""
    builder = InlineKeyboardBuilder()

    # Причины (можно вынести в константы, но пока здесь)
    # ID: Text
    reasons = {
        1: "Курьер сильно задерживает заказ",
        2: "Курьер нагрубил получателю",
        3: "Курьер не доставил заказ",
        4: "Курьер повредил заказ",
    }

    for r_id, text in reasons.items():
        builder.button(
            text=text,
            callback_data=DisputeReasonCallback(
                reason_id=r_id, order_id=order_id, page=page, status=status
            ).pack(),
        )

    builder.adjust(1)

    # Кнопка отмены
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=OrderDetailCallback(
                order_id=order_id, from_page=page, from_status=status
            ).pack(),
        )
    )

    return builder.as_markup()


def get_dispute_created_keyboard(
    order_id: int, dispute_id: int, page: int = 1, status: str = "all"
) -> InlineKeyboardMarkup:
    """Клавиатура после создания спора."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📄 Карточка спора",
        callback_data=OrderActionCallback(
            order_id=order_id, action="view_dispute", page=page, status=status
        ).pack(),
    )
    # Возможно, "Отменить" здесь не нужна, если есть карточка спора, но по ТЗ написано
    # "Отменить" - скорее всего отменить СПОР, а не действие
    builder.button(
        text="❌ Отменить спор",
        callback_data=OrderRefundCallback(
            dispute_id=dispute_id, action="cancel_dispute", page=page, status=status
        ).pack(),
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="shop_main_menu"))
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Вернуться к заказу",
            callback_data=OrderDetailCallback(
                order_id=order_id, from_page=page, from_status=status
            ).pack(),
        )
    )

    return builder.as_markup()


def get_dispute_card_keyboard(
    order_id: int,
    dispute_id: int,
    can_cancel: bool = False,
    page: int = 1,
    status: str = "all",
    source: str | None = None,
) -> InlineKeyboardMarkup:
    """Клавиатура карточки спора."""
    builder = InlineKeyboardBuilder()

    if can_cancel:
        builder.button(
            text="❌ Отменить спор",
            callback_data=OrderRefundCallback(
                dispute_id=dispute_id, action="cancel_dispute", page=page, status=status
            ).pack(),
        )

    builder.button(
        text="К заказу",
        callback_data=OrderDetailCallback(
            order_id=order_id, from_page=page, from_status=status, source="dispute"
        ).pack(),
    )

    # Кнопка назад к списку споров или к заказу
    if source == "order":
        back_callback = OrderDetailCallback(
            order_id=order_id, from_page=page, from_status=status
        ).pack()
    else:
        # Default to disputes list
        back_callback = DisputesListCallback(page=page, status=status).pack()

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=back_callback,
        )
    )

    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="shop_main_menu"))
    return builder.as_markup()


def get_disputes_list_keyboard(
    disputes: list[dict],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Генерация клавиатуры со списком споров."""
    builder = InlineKeyboardBuilder()

    status_map = {
        "PENDING_REVIEW": "⏳",
        "IN_REVIEW": "👀",
        "RESOLVED": "✅",
        "CANCELLED": "🚫",
    }

    for d in disputes:
        d_id = d.get("id")
        order_id = d.get("order_id")
        status = d.get("status")
        icon = status_map.get(status, "❓")

        # Текст кнопки: Заказ #Order | Icon | Спор #ID
        button_text = f"Заказ #{order_id} | {icon} | Спор #{d_id}"

        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=OrderActionCallback(
                    order_id=order_id, action="view_dispute", page=page, status="all"
                ).pack(),
            )
        )

    # Пагинация
    pagination_row = []
    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=DisputesListCallback(page=page - 1).pack(),
            )
        )

    pagination_row.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=DisputesListCallback(page=page + 1).pack(),
            )
        )

    if pagination_row:
        builder.row(*pagination_row)

    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="shop_main_menu"))

    return builder.as_markup()
