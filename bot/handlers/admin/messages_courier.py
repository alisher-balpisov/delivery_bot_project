# messages_couriers.py — Тексты сообщений для хендлеров курьеров


def couriers_list_text(total: int) -> str:
    return f"📋 <b>Список курьеров</b>\nВсего: {total}"


def couriers_list_error() -> str:
    return "Ошибка при загрузке списка курьеров"


def courier_card_text(
    full_name: str | None,
    username: str | None,
    phones: str,
    rating: float | None,
    is_active: bool,
    status: str,
) -> str:
    username_text = f"@{username}" if username else "Нет"
    rating_text = f"{rating:.1f} ⭐️" if rating else "Нет оценок"
    status_emoji = f"🟢 На смене {is_active}" if is_active else "🔴 Не на смене"

    name = full_name.split()[1] if full_name else "Не указано"

    return (
        f"👤 <b>Курьер: {name}</b>\n\n"
        f"📱 Телеграм: {username_text}\n"
        f"📞 Телефон: {phones}\n"
        f"⭐️ Рейтинг: {rating_text}\n"
        f"🔄 Статус смены: {status_emoji}\n"
        f"🔒 Статус аккаунта: {status}\n"
    )


def courier_card_error() -> str:
    return "Не удалось загрузить данные курьера"


def courier_history_text(total: int) -> str:
    return f"📜 <b>История заказов (Всего: {total})</b>\nВыберите заказ для просмотра деталей:"


def courier_history_empty() -> str:
    return "📭 История заказов пуста"


def courier_history_error() -> str:
    return "Не удалось загрузить историю заказов"


def courier_order_detail_error() -> str:
    return "Не удалось загрузить детали заказа"
