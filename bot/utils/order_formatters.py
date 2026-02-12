import html

from bot.utils.formatters import format_dt_short


def format_order_details(order: dict) -> str:
    """
    Форматирует детали заказа в едином стиле для всех ролей.

    Args:
        order: Словарь с данными заказа

    Returns:
        Отформатированная строка с деталями заказа
    """
    order_id = order.get("id")
    status = order.get("status") or "Не указан"
    price = order.get("price", 0)
    try:
        price_val = int(float(price))
    except (ValueError, TypeError):
        price_val = price

    created_at = format_dt_short(order.get("created_at", ""))
    updated_at = format_dt_short(order.get("updated_at", ""))
    description = html.escape(order.get("description") or "Нет описания")

    shop = order.get("shop")
    shop_name = html.escape(shop.get("name")) if shop else "Не указан"

    courier = order.get("courier")
    courier_name = html.escape(courier.get("full_name")) if courier else "Не назначен"

    extra_info = ""
    if order.get("courier_notes"):
        courier_notes = html.escape(order.get("courier_notes"))
        extra_info += f"\n🗒 <b>Заметки курьера:</b> {courier_notes}"

    # Заметки (notes)
    notes = order.get("notes")
    if notes:
        if isinstance(notes, list):
            extra_info += "\n\n📝 <b>Заметки:</b>"
            for note in notes:
                if isinstance(note, dict):
                    author = note.get("author_role", "Система")
                    author_name = (
                        "Магазин"
                        if author == "shop"
                        else ("Курьер" if author == "courier" else author)
                    )
                    content = html.escape(note.get("content", ""))
                    created = format_dt_short(note.get("created_at", ""))
                    extra_info += f"\n• {created} ({author_name}): {content}"
                else:
                    extra_info += f"\n• {html.escape(str(note))}"
        else:
            extra_info += f"\n\n📝 <b>Заметки:</b> {html.escape(str(notes))}"

    # История изменений (order_history)
    order_history = order.get("order_history")
    if order_history and isinstance(order_history, list):
        extra_info += "\n\n📜 <b>История изменений:</b>"
        for entry in order_history:
            if isinstance(entry, dict):
                dt = format_dt_short(entry.get("created_at", ""))
                c_type = entry.get("change_type", "Изменение")
                extra_info += f"\n• {dt} — {c_type}"

    text = (
        f"📦 <b>Заказ #{order_id}</b>\n\n"
        f"📝 <b>Описание:</b> {description}\n"
        f"💰 <b>Цена:</b> {price_val} ₸\n"
        f"📊 <b>Статус:</b> {f'<u>{status}</u>' if status == 'disputed' or status == 'awaiting_confirmation' else status}\n"
        f"🏪 <b>Магазин:</b> {shop_name}\n"
        f"👤 <b>Курьер:</b> {courier_name}\n"
        f"📅 <b>Создан:</b> {created_at}\n"
        f"🔄 <b>Обновлен:</b> {updated_at}"
        f"{extra_info}\n"
    )

    return text
