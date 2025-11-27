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
    status = order.get("status", "unknown")
    price = order.get("price", 0)
    # Обработка цены, если она пришла как строка или число
    try:
        price_val = int(float(price))
    except (ValueError, TypeError):
        price_val = price

    created_at = format_dt_short(order.get("created_at", ""))
    updated_at = format_dt_short(order.get("updated_at", ""))
    description = order.get("description") or "Нет описания"

    recipient_address = order.get("recipient_address") or "Нет адреса"
    recipient_phone = order.get("recipient_phone") or "Нет телефона"
    client_phone = order.get("client_phone") or "Нет телефона"

    # Данные магазина
    shop = order.get("shop")
    shop_name = shop.get("name") if shop else "Не указан"

    # Данные курьера
    courier = order.get("courier")
    courier_name = courier.get("full_name") if courier else "Не назначен"

    # Дополнительная информация
    extra_info = ""
    if order.get("courier_notes"):
        extra_info += f"\n🗒 <b>Заметки курьера:</b> {order.get('courier_notes')}"

    text = (
        f"📦 <b>Заказ #{order_id}</b>\n\n"
        f"📝 <b>Описание:</b> {description}\n"
        f"💰 <b>Цена:</b> {price_val} ₸\n"
        f"📊 <b>Статус:</b> {status}\n"
        f"📍 <b>Адрес:</b> {recipient_address}\n"
        f"📞 <b>Телефон получателя:</b> {recipient_phone}\n"
        f"📱 <b>Телефон клиента:</b> {client_phone}\n"
        f"🏪 <b>Магазин:</b> {shop_name}\n"
        f"👤 <b>Курьер:</b> {courier_name}\n"
        f"📅 <b>Создан:</b> {created_at}\n"
        f"🔄 <b>Обновлен:</b> {updated_at}"
        f"{extra_info}\n"
    )

    return text
