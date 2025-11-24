"""
Упрощенный фильтр для предоставления UserDTO.

Ключевые изменения:
- Убрана зависимость от UsersClient для получения профиля
- Используется только Redis для кэширования
- Улучшена логика определения статуса пользователя
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.auth_client import AuthClient
from bot.dto import UserDTO
from bot.redis_storage import UserCacheData, UserDataStorage
from bot.utils.helpers import parse_user_role

logger = get_logger(__name__)


class UserDataFilter(BaseFilter):
    """
    Фильтр-провайдер данных пользователя через Redis.

    Логика работы:
    1. Проверяет наличие данных в Redis
    2. Если данных нет - пытается получить через login()
    3. Если login() не удался - создает DTO гостя
    4. Возвращает UserDTO для использования в хендлерах
    """

    def __init__(self, storage: UserDataStorage):
        self.storage = storage

    async def __call__(
        self,
        event: TelegramObject,
        auth_client: AuthClient,
    ) -> dict[str, Any] | bool:
        """
        Основной метод фильтра.

        Returns:
            Словарь с user (UserDTO) для использования в хендлерах
        """
        if not isinstance(event, (Message, CallbackQuery)) or not event.from_user:
            return False

        telegram_id = event.from_user.id
        username = event.from_user.username

        # Пытаемся получить данные из Redis
        user_data = await self.storage.get_user_data(telegram_id)

        if user_data:
            # Данные есть в кэше
            logger.debug(f"Данные пользователя {telegram_id} получены из Redis")

            # Если пользователь GUEST, проверяем, не пора ли обновить данные
            if user_data.role == UserRole.GUEST:
                should_retry_login = False
                if not user_data.cached_at:
                    should_retry_login = True
                elif datetime.now(UTC) - user_data.cached_at > timedelta(seconds=30):
                    should_retry_login = True

                if should_retry_login:
                    logger.debug(f"Кэш гостя устарел для {telegram_id}, пробуем login")
                    login_result = await auth_client.login(telegram_id)

                    if login_result.success and isinstance(login_result.data, dict):
                        # Успешный login - обновляем данные
                        user_dto = await self._handle_successful_login(
                            telegram_id, username, login_result.data
                        )
                        return {"user": user_dto}
                    else:
                        # Login снова не удался - обновляем активность но держим короткий TTL
                        # Обновляем cached_at чтобы не спамить попытками каждую секунду
                        await self.storage.update_user_data(
                            telegram_id,
                            {
                                "last_activity": datetime.now(UTC).isoformat(),
                                "cached_at": datetime.now(UTC).isoformat(),
                            },
                            ttl=300,
                        )
                        user_dto = self._create_dto_from_cache(user_data, username)
                        return {"user": user_dto}

                # Если кэш свежий, просто обновляем активность с коротким TTL
                await self.storage.update_activity(telegram_id, ttl=300)
                user_dto = self._create_dto_from_cache(user_data, username)
                return {"user": user_dto}

            # Для обычных пользователей обновляем активность со стандартным TTL
            await self.storage.update_activity(telegram_id)

            # Создаем DTO
            user_dto = self._create_dto_from_cache(user_data, username)
            return {"user": user_dto}

        # Данных нет - пытаемся получить через login
        logger.debug(f"Данные пользователя {telegram_id} отсутствуют, пробуем login")

        login_result = await auth_client.login(telegram_id)

        if login_result.success and isinstance(login_result.data, dict):
            # Успешный login - сохраняем данные и создаем DTO
            user_dto = await self._handle_successful_login(telegram_id, username, login_result.data)
            return {"user": user_dto}

        # Login не удался - создаем гостя
        status_code = login_result.status_code
        logger.info(f"Login не удался для {telegram_id} (код: {status_code}), создаем гостя")

        user_dto = await self._create_guest(telegram_id, username)
        return {"user": user_dto}

    def _create_dto_from_cache(self, user_data: UserCacheData, username: str | None) -> UserDTO:
        """Создает UserDTO из кэшированных данных"""
        return UserDTO(
            user_id=user_data.user_id,
            telegram_id=user_data.telegram_id,
            name=user_data.name,
            role=user_data.role,
        )

    async def _handle_successful_login(
        self, telegram_id: int, username: str | None, response_data: dict
    ) -> UserDTO:
        """
        Обрабатывает успешный login:
        - Сохраняет токены
        - Сохраняет данные пользователя
        - Создает DTO
        """
        user_info = response_data.get("user", {})

        # Создаем объект данных пользователя
        user_data = UserCacheData(
            user_id=user_info.get("id"),
            telegram_id=telegram_id,
            name=user_info.get("name"),
            role=parse_user_role(user_info.get("role")),
            username=username,
            cached_at=datetime.now(UTC),  # Явно устанавливаем время кэширования
        )

        # Сохраняем токены
        await self.storage.save_tokens(
            telegram_id=telegram_id,
            access_token=response_data["access_token"],
            refresh_token=response_data["refresh_token"],
            access_expires_in=response_data["expires_in"],
            refresh_expires_in=response_data["refresh_expires_in"],
        )

        # Сохраняем данные пользователя
        await self.storage.save_user_data(telegram_id, user_data)

        logger.info(f"Данные пользователя {telegram_id} сохранены после login")

        # Создаем DTO
        return UserDTO(
            user_id=user_data.user_id,
            telegram_id=user_data.telegram_id,
            name=user_data.name,
            role=user_data.role,
        )

    async def _create_guest(self, telegram_id: int, username: str | None) -> UserDTO:
        """
        Создает гостя и сохраняет его в Redis.

        Это позволяет избежать повторных запросов к API
        для незарегистрированных пользователей.
        """
        user_data = UserCacheData(
            user_id=None,
            telegram_id=telegram_id,
            name=None,
            role=UserRole.GUEST,
            username=username,
            cached_at=datetime.now(UTC),  # Явно устанавливаем время кэширования
        )

        # Сохраняем гостя в Redis с коротким TTL (5 минут)
        await self.storage.save_user_data(telegram_id, user_data, ttl=300)

        logger.debug(f"Создан гость для {telegram_id}")

        return UserDTO(
            user_id=None,
            telegram_id=telegram_id,
            name=None,
            role=UserRole.GUEST,
        )


__all__ = ["UserDataFilter"]
