# api_helper.py — Централизованные утилиты для взаимодействия с API
from collections.abc import Callable
from typing import Any

from backend.src.core.logging import get_logger
from bot.utils.token_manager import TokenManager

logger = get_logger(__name__)


async def execute_api_call(
    token_manager: TokenManager, user_id: int, func: Callable[..., Any], **kwargs
) -> Any:
    """
    Выполняет API-запрос с автоматическим обновлением токена при 401 ошибке.

    Args:
        token_manager: Объект для управления токенами доступа
        user_id: Telegram ID пользователя
        func: Функция-клиент API (например, orders_client.get_order_details)
        **kwargs: Аргументы для функции API

    Returns:
        Результат выполнения функции API
    """
    token = await token_manager.get_token(user_id)
    result = await func(token=token, **kwargs)

    # Если токен истек (401), пробуем обновить и повторить запрос
    if result.status_code == 401:
        logger.info(f"Token expired for user {user_id}, attempting refresh...")
        token = await token_manager.get_token(user_id, force_refresh=True)
        if token:
            result = await func(token=token, **kwargs)
        else:
            logger.error(f"Failed to refresh token for user {user_id}")

    if not result.success:
        detail = getattr(result, "detail", None) or (
            result.data.get("detail") if result.data else "Unknown error"
        )
        logger.warning(f"API call failed: {func.__name__} - {detail}")

    return result
