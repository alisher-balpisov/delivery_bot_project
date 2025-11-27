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
