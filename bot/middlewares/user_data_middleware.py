from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from bot.clients import client_manager

logger = get_logger(__name__)


class UserDataMiddleware(BaseMiddleware):
    """
    Middleware для извлечения и предоставления данных пользователя из FSM
    во все обработчики, с восстановлением данных из API при необходимости.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state: FSMContext = data.get("state")
        user_data = {}

        if state:
            try:
                user_data = await state.get_data()
            except Exception as e:
                logger.error(f"Ошибка получения данных FSM: {e}")

        # Если данные пустые и есть telegram_id, пытаемся восстановить из API
        if not user_data and hasattr(event, "from_user") and event.from_user:
            await self._restore_user_data(state, event, user_data)

        # Добавляем user_data в контекст для всех обработчиков
        data["user_data"] = user_data

        return await handler(event, data)

    async def _restore_user_data(self, state: FSMContext, event: TelegramObject, user_data: dict):
        """Восстанавливает данные пользователя из API."""
        try:
            telegram_id = event.from_user.id
            user_profile = await client_manager.users.get_user_profile(telegram_id)

            if user_profile and user_profile.get("success") is not False:
                # Если данные еще не сохранены в state, восстанавливаем из БД
                if not user_data:
                    # Проверяем, был ли пользователь авторизован ранее по access_token
                    # В реальности access_token не хранится вечноз, поэтому восстановим role и user_id
                    await state.update_data(
                        role=user_profile.get("role", "guest"),
                        user_id=user_profile.get("id"),
                        name=user_profile.get("name", ""),
                        telegram_id=telegram_id,
                    )
                    logger.info(f"Восстановлены данные пользователя {telegram_id} из БД")
            else:
                # Если профиля нет или ошибка, сохраняем как гостя
                if not user_data:
                    await state.update_data(role=UserRole.GUEST, telegram_id=telegram_id)
        except Exception as e:
            logger.error(f"Ошибка восстановления данных пользователя: {e}")
