import html
from datetime import datetime
from typing import Any

from bot.constants import MAX_CODES_DISPLAY
from bot.messages import AdminServiceMessages


def format_codes_as_html_table(codes: list[dict[str, Any]]) -> str:
    """
    Форматирует список кодов регистрации в виде HTML-таблицы для Telegram.

    Args:
        codes: Список словарей с данными о кодах.

    Returns:
        Строка с отформатированной HTML-таблицей.
    """
    if not codes:
        return "<i>Активных кодов регистрации не найдено.</i>"

    header = html.escape(AdminServiceMessages.CODE_TABLE_HEADER)

    lines = []
    for c in codes[:MAX_CODES_DISPLAY]:
        code = html.escape(c.get("code", "?")).ljust(12)
        role = html.escape(c.get("role", "?")).ljust(12)
        status = AdminServiceMessages.USED if c.get("is_used") else AdminServiceMessages.NOT_USED
        status = html.escape(status).ljust(15)
        lines.append(f"{code}{role}{status}")

    table_body = "\n".join(lines)
    table = f"<pre>{header}\n{'-' * len(header)}\n{table_body}</pre>"
    text = AdminServiceMessages.CODES_HEADER + table
    if len(codes) > MAX_CODES_DISPLAY:
        text += AdminServiceMessages.MORE_CODES.format(len(codes) - MAX_CODES_DISPLAY)

    return text


def format_dt(dt: str) -> str:
    if not dt:
        return "—"
    try:
        return datetime.fromisoformat(dt.replace("Z", "")).strftime("%d.%m.%Y  %H:%M")
    except Exception:
        return dt


def format_dt_short(dt: str) -> str:
    """
    Форматирует дату и время в короткий формат (dd.mm HH:MM).
    """
    if not dt:
        return "—"
    try:
        return datetime.fromisoformat(dt.replace("Z", "")).strftime("%d.%m %H:%M")
    except Exception:
        return dt


def format_courier_card(courier: dict[str, Any]) -> str:
    """
    Форматирует карточку курьера (унифицированный вид).
    """
    full_name = courier.get("full_name")
    headers = full_name.split() if full_name else []
    display_name = headers[1] if len(headers) > 1 else (full_name or "Не указано")

    username = courier.get("username")
    username_text = f"@{username}" if username else "Нет"

    phones_data = courier.get("phone_numbers", [])
    if isinstance(phones_data, list):
        phones = ", ".join(phones_data) or "Нет"
    else:
        phones = str(phones_data)

    rating = courier.get("rating")
    rating_text = f"{rating:.1f} ⭐️" if rating else "Нет оценок"

    status_emoji = "🟢 На смене" if courier.get("is_active") else "🔴 Не на смене"
    user_status = courier.get("status", "unknown")

    text = (
        f"👤 <b>Курьер: {display_name}</b>\n\n"
        f"📱 Телеграм: {username_text}\n"
        f"📞 Телефон: {phones}\n"
        f"⭐️ Рейтинг: {rating_text}\n"
        f"🔄 Статус смены: {status_emoji}\n"
        f"🔒 Статус аккаунта: {user_status}\n"
    )
    return text


def format_role_name(role: str) -> str:
    """Преобразует роль пользователя в читаемый формат."""
    role_names = {
        "shop": "🏪 Магазин",
        "courier": "👤 Курьер",
        "admin": "👑 Администратор",
    }
    return role_names.get(role.lower(), role)


def format_dispute_details(dispute: dict[str, Any], templates: Any = None) -> str:
    """
    Форматирует детали спора для отображения.
    """
    dispute_id = dispute.get("id")
    order_id = dispute.get("order_id")
    status = dispute.get("status", "unknown")
    shop_name = dispute.get("shop_name") or "Не указан"
    full_name = dispute.get("courier_full_name")
    courier_name = (
        full_name.split()[1] if (full_name and len(full_name.split()) > 1) else "Не указан"
    )
    opened_by_role = dispute.get("opened_by_role", "unknown")
    description = dispute.get("description", "Нет описания")
    created_at = format_dt_short(dispute.get("created_at", ""))
    resolved_at = dispute.get("resolved_at")

    # Стилизация статуса
    status_emoji = "⚪"
    status_label = status

    if templates:
        status_emoji = getattr(templates, "DISPUTE_STATUS_EMOJIS", {}).get(status, "⚪")
        status_label = getattr(templates, "DISPUTE_STATUS_LABELS", {}).get(status, status)

    resolved_at_str = format_dt_short(resolved_at) if resolved_at else "—"

    template = getattr(
        templates,
        "DISPUTE_DETAILS_TEMPLATE",
        "<b>Спор #{dispute_id}</b> (Заказ #{order_id})\n\n"
        "Статус: {status_emoji} {status}\n"
        "Магазин: {shop_name}\n"
        "Курьер: {courier_name}\n"
        "Открыт: {opened_by_role}\n"
        "Создан: {created_at}\n"
        "Завершен: {resolved_at}\n\n"
        "Описание: <i>{description}</i>",
    )

    return template.format(
        dispute_id=dispute_id,
        order_id=order_id,
        status_emoji=status_emoji,
        status=status_label,
        shop_name=shop_name,
        courier_name=courier_name,
        opened_by_role=format_role_name(opened_by_role),
        created_at=created_at,
        resolved_at=resolved_at_str,
        description=description,
    )
