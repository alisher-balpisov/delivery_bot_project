from typing import Any

from backend.src.core.logging import get_logger
from bot.constants import MAX_MESSAGE_LENGTH, ROLE_EMOJI_MAP, STATS_EMOJIS, UserRole
from bot.exceptions import ErrorMessages
from bot.messages import AdminServiceMessages

logger = get_logger(__name__)


def parse_user_role(role: Any) -> UserRole:
    """Безопасно парсит строку роли в UserRole enum, с fallback в GUEST."""
    if not isinstance(role, str):
        return UserRole.GUEST
    try:
        return UserRole(role)
    except ValueError:
        logger.warning(
            f"Получена неизвестная роль '{role!s}' от API. Устанавливается роль GUEST по умолчанию."
        )
        return UserRole.GUEST


def format_stats_message(stats: dict[str, Any]) -> str:
    """Формирование сообщения системной статистики."""
    if not stats or not isinstance(stats, dict):
        return ErrorMessages.Stats.STATS_RETRIEVAL_ERROR

    lines = [AdminServiceMessages.STATS_HEADER]
    user_stats = [
        AdminServiceMessages.USERS_STATS.format(
            emoji=STATS_EMOJIS["users"], count=stats.get("total_users", 0)
        ),
        AdminServiceMessages.ADMIN_STATS.format(
            emoji=ROLE_EMOJI_MAP[UserRole.ADMIN], count=stats.get("total_admins", 0)
        ),
        AdminServiceMessages.SHOPS_STATS.format(
            emoji=ROLE_EMOJI_MAP[UserRole.SHOP], count=stats.get("total_shops", 0)
        ),
        AdminServiceMessages.COURIERS_STATS.format(
            emoji=ROLE_EMOJI_MAP[UserRole.COURIER], count=stats.get("total_couriers", 0)
        ),
    ]
    lines.extend(user_stats)
    lines.append("")
    order_stats = [
        AdminServiceMessages.ORDERS_STATS.format(
            emoji=STATS_EMOJIS["orders"], count=stats.get("total_orders", 0)
        ),
        AdminServiceMessages.ACTIVE_ORDERS_STATS.format(
            emoji=STATS_EMOJIS["active_orders"], count=stats.get("active_orders", 0)
        ),
        AdminServiceMessages.COMPLETED_ORDERS_STATS.format(
            emoji=STATS_EMOJIS["completed_orders"], count=stats.get("completed_orders", 0)
        ),
        AdminServiceMessages.CANCELLED_ORDERS_STATS.format(
            emoji=STATS_EMOJIS["cancelled_orders"], count=stats.get("cancelled_orders", 0)
        ),
    ]
    lines.extend(order_stats)
    lines.append("")
    dispute_stats = [
        AdminServiceMessages.DISPUTES_STATS.format(
            emoji=STATS_EMOJIS["disputes"], count=stats.get("total_disputes", 0)
        ),
        AdminServiceMessages.UNRESOLVED_DISPUTES_STATS.format(
            emoji=STATS_EMOJIS["unresolved_disputes"], count=stats.get("unresolved_disputes", 0)
        ),
    ]
    lines.extend(dispute_stats)
    message = "\n".join(lines)

    if len(message) > MAX_MESSAGE_LENGTH:
        logger.warning("Сообщение статистики было обрезано")
        return message[: MAX_MESSAGE_LENGTH - 100] + AdminServiceMessages.MESSAGE_TRUNCATED

    return message
