from typing import Any

import httpx

from backend.src.core.config import get_bot_token
from backend.src.core.logging import get_logger

from .schemas import NotificationRequest

logger = get_logger(__name__)


async def send_telegram_message(notification: NotificationRequest) -> bool:
    """Отправляет одно Telegram-сообщение через Bot API."""
    url = f"https://api.telegram.org/bot{get_bot_token()}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": notification.telegram_id,
        "text": notification.text,
        "disable_web_page_preview": notification.disable_web_page_preview,
    }
    if notification.parse_mode:
        payload["parse_mode"] = notification.parse_mode

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
        if response.status_code != 200:
            logger.warning(
                "Telegram notification failed: %s %s",
                response.status_code,
                response.text[:300],
            )
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("Telegram notification request failed: %s", exc)
        return False
