import httpx
from backend.src.common.enums import DisputeStatus, UserRole
from backend.src.core.logging import get_logger
from bot.clients import client_manager
from bot.constants import ROLE_EMOJI_MAP, ErrorMessages
from bot.messages import CommonMessages, CommonServiceMessages, DisputeMessages

logger = get_logger(__name__)


async def get_api_status_text() -> str:
    """Проверяет состояние API и возвращает отформатированный текст."""
    try:
        data = await client_manager.system.health_check()
        if data and data.get("status") == "ok":
            return CommonMessages.API_STATUS_TEMPLATE.format(status=data.get("status"))
        return ErrorMessages.API.API_ERROR(
            detail=data.get("detail", CommonServiceMessages.API_STATUS_ERROR)
        )
    except httpx.RequestError as e:
        return ErrorMessages.API.CONNECTION_ERROR(error=e)
    except Exception as e:
        logger.error(CommonServiceMessages.UNEXPECTED_ERROR.format(e), exc_info=True)
        return ErrorMessages.API.UNEXPECTED_ERROR


def get_orders_text_by_role(role: UserRole) -> str:
    """Возвращает текст о заказах в зависимости от роли пользователя."""
    if role == UserRole.SHOP:
        return CommonServiceMessages.SHOP_ORDERS.format(ROLE_EMOJI_MAP[UserRole.SHOP])
    elif role == UserRole.COURIER:
        return CommonServiceMessages.COURIER_ORDERS.format(ROLE_EMOJI_MAP[UserRole.COURIER])
    elif role == UserRole.ADMIN:
        return CommonServiceMessages.ADMIN_ORDERS.format(ROLE_EMOJI_MAP[UserRole.ADMIN])
    return ErrorMessages.Orders.NO_ORDERS_FOUND


def get_new_dispute_text() -> str:
    """Возвращает инструкцию по созданию нового спора."""
    return DisputeMessages.NEW_DISPUTE_PROMPT.format(status=DisputeStatus.OPEN.value)


async def get_user_disputes_text(telegram_id: int) -> str:
    """Получает споры пользователя и возвращает отформатированный текст."""
    try:
        disputes = await client_manager.disputes.get_my_disputes(telegram_id)
        if not disputes:
            return DisputeMessages.NO_DISPUTES

        text_lines = [DisputeMessages.DISPUTES_HEADER]
        for dispute in disputes[:5]:
            status = DisputeStatus(dispute.get("status", "closed"))
            status_emoji = {
                DisputeStatus.OPEN: CommonServiceMessages.DISPUTE_STATUS_OPEN,
                DisputeStatus.IN_REVIEW: CommonServiceMessages.DISPUTE_STATUS_IN_REVIEW,
                DisputeStatus.RESOLVED: CommonServiceMessages.DISPUTE_STATUS_RESOLVED,
                DisputeStatus.CLOSED: CommonServiceMessages.DISPUTE_STATUS_CLOSED,
            }.get(status, CommonServiceMessages.DISPUTE_STATUS_DEFAULT)
            line = CommonServiceMessages.DISPUTE_LINE.format(
                dispute.get("id", 0), status_emoji, status.value
            )
            text_lines.append(line)

        return "\n".join(text_lines)

    except Exception as e:
        logger.error(CommonServiceMessages.DISPUTES_ERROR.format(telegram_id, e), exc_info=True)
        return ErrorMessages.Disputes.DISPUTES_LOAD_ERROR
