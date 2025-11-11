import httpx
from backend.src.common.enums import DisputeStatus, UserRole
from backend.src.core.logging import get_logger
from bot.clients.disputes_client import DisputesClient
from bot.clients.system_client import SystemClient
from bot.constants import ROLE_EMOJI_MAP
from bot.exceptions import ErrorMessages
from bot.messages import CommonMessages, CommonServiceMessages, DisputeMessages

logger = get_logger(__name__)


async def get_api_status_text(system_client: SystemClient) -> str:
    """Проверяет состояние API и возвращает отформатированный текст."""
    try:
        result = await system_client.health_check()
        if result.success and isinstance(result.data, dict):
            health_data = result.data
            return CommonMessages.API_STATUS_TEMPLATE.format(
                status=health_data.get("status", "N/A"),
                app=health_data.get("app", "N/A"),
                version=health_data.get("version", "N/A"),
                timestamp=health_data.get("timestamp", "N/A"),
            )
        else:
            detail = result.detail or CommonServiceMessages.API_STATUS_ERROR
            return ErrorMessages.API.API_ERROR(detail=detail)
    except httpx.RequestError as e:
        return ErrorMessages.API.CONNECTION_ERROR(error=e)
    except Exception as e:
        logger.error(CommonServiceMessages.UNEXPECTED_ERROR.format(e), exc_info=True)
        return ErrorMessages.API.UNEXPECTED_ERROR


def get_orders_text_by_role(role: UserRole) -> str:
    """Возвращает текст о заказах в зависимости от роли пользователя."""
    role_map = {
        UserRole.SHOP: CommonServiceMessages.SHOP_ORDERS.format(ROLE_EMOJI_MAP.get(UserRole.SHOP)),
        UserRole.COURIER: CommonServiceMessages.COURIER_ORDERS.format(
            ROLE_EMOJI_MAP.get(UserRole.COURIER)
        ),
        UserRole.ADMIN: CommonServiceMessages.ADMIN_ORDERS.format(
            ROLE_EMOJI_MAP.get(UserRole.ADMIN)
        ),
    }
    return role_map.get(role, ErrorMessages.Orders.NO_ORDERS_FOUND)


def get_new_dispute_text() -> str:
    """Возвращает инструкцию по созданию нового спора."""
    return DisputeMessages.NEW_DISPUTE_PROMPT.format(status=DisputeStatus.OPEN.value)


async def get_user_disputes_text(token: str | None, disputes_client: DisputesClient) -> str:
    """Получает споры пользователя и возвращает отформатированный текст."""
    if not token:
        return ErrorMessages.Auth.UNAUTHORIZED
    try:
        result = await disputes_client.get_my_disputes(token)
        if not result.success or not isinstance(result.data, list):
            return ErrorMessages.Disputes.DISPUTES_LOAD_ERROR

        disputes = result.data
        if not disputes:
            return DisputeMessages.NO_DISPUTES

        status_emoji_map = {
            DisputeStatus.OPEN: CommonServiceMessages.DISPUTE_STATUS_OPEN,
            DisputeStatus.IN_REVIEW: CommonServiceMessages.DISPUTE_STATUS_IN_REVIEW,
            DisputeStatus.RESOLVED: CommonServiceMessages.DISPUTE_STATUS_RESOLVED,
            DisputeStatus.CLOSED: CommonServiceMessages.DISPUTE_STATUS_CLOSED,
        }

        text_lines = [DisputeMessages.DISPUTES_HEADER]
        for dispute in disputes[:10]:
            status = DisputeStatus(dispute.get("status", "closed"))
            status_emoji = status_emoji_map.get(
                status, CommonServiceMessages.DISPUTE_STATUS_DEFAULT
            )
            line = CommonServiceMessages.DISPUTE_LINE.format(
                dispute.get("id", 0), status_emoji, status.value
            )
            text_lines.append(line)

        return "\n".join(text_lines)

    except Exception as e:
        logger.error(CommonServiceMessages.DISPUTES_ERROR.format(e), exc_info=True)
        return ErrorMessages.Disputes.DISPUTES_LOAD_ERROR
