# Файл: bot/user_data_middleware.py (НОВЫЙ ФАЙЛ)

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from backend.src.core.logging import get_logger
from cryptography.fernet import Fernet, InvalidToken

logger = get_logger(__name__)


class UserDataMiddleware(BaseMiddleware):
    """
    Middleware для извлечения и предоставления данных пользователя из FSM
    во все обработчики.
    """

    def __init__(self, encryption_key: str | None = None):
        self.fernet = Fernet(encryption_key.encode()) if encryption_key else None

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Расшифровка токена"""
        if self.fernet:
            try:
                return self.fernet.decrypt(encrypted_token.encode()).decode()
            except InvalidToken:
                logger.warning("Не удалось расшифровать токен при извлечении user_data")
                return ""
        return encrypted_token

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state = data.get("state")
        user_data = {}

        if state:
            try:
                user_data = await state.get_data()
                if user_data.get("access_token_encrypted") and self.fernet:
                    encrypted_token = user_data["access_token_encrypted"]
                    user_data["access_token"] = self._decrypt_token(encrypted_token)
            except Exception as e:
                logger.error(f"Ошибка получения данных FSM: {e}")

        # Добавляем user_data в контекст для всех обработчиков
        data["user_data"] = user_data

        return await handler(event, data)
