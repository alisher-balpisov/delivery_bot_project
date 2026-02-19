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
        # L1 Кэш в памяти для экстремальной скорости
        self._l1_cache = {}
        self._l1_cache_ttl = 30  # 30 секунд

    async def __call__(
        self,
        event: TelegramObject,
        auth_client: AuthClient,
    ) -> dict[str, Any] | bool:
        """
        Основной метод фильтра.

        Returns:
            Словарь с user (UserDTO) и user_data (UserCacheData) для использования в хендлерах
        """
        if not isinstance(event, (Message, CallbackQuery)) or not event.from_user:
            return False

        telegram_id = event.from_user.id
        username = event.from_user.username

        # Проверяем L1 кэш для текущего сообщения
        now = datetime.now(UTC)
        cache_key = f"u_{telegram_id}"
        if cache_key in self._l1_cache:
            cached_time, cached_data = self._l1_cache[cache_key]
            if (now - cached_time).total_seconds() < self._l1_cache_ttl:
                return cached_data

        # Пытаемся получить данные из Redis
        user_data = await self.storage.get_user_data(telegram_id)

        if user_data:
            # Обновляем активность (троттлинг 2 минуты)
            if not user_data.last_activity or (
                now - user_data.last_activity > timedelta(minutes=2)
            ):
                await self.storage.update_activity_optimized(telegram_id)

            user_dto = self._create_dto_from_cache(user_data, username)
            result = {"user": user_dto, "user_data": user_data}

            # Сохраняем в L1 кэш
            self._l1_cache[cache_key] = (now, result)
            return result

        # Данных нет - пытаемся получить через login
        logger.debug(f"Данные пользователя {telegram_id} отсутствуют, пробуем login")

        login_result = await auth_client.login(telegram_id)

        if login_result.success and isinstance(login_result.data, dict):
            # Успешный login - сохраняем данные и создаем DTO
            user_dto, new_user_data = await self._handle_successful_login(
                telegram_id, username, login_result.data
            )
            result = {"user": user_dto, "user_data": new_user_data}

            # Сохраняем в L1 кэш
            self._l1_cache[cache_key] = (now, result)
            return result

        # Login не удался - создаем гостя
        status_code = login_result.status_code
        logger.info(f"Login не удался для {telegram_id} (код: {status_code}), создаем гостя")

        user_dto, guest_user_data = await self._create_guest(telegram_id, username)
        return {"user": user_dto, "user_data": guest_user_data}

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
    ) -> tuple[UserDTO, UserCacheData]:
        """
        Обрабатывает успешный login:
        - Сохраняет токены и данные пользователя за ОДНУ запись в Redis
        - Создает DTO
        """
        user_info = response_data.get("user", {})
        now = datetime.now(UTC)
        expires_in = response_data["expires_in"]
        refresh_expires_in = response_data["refresh_expires_in"]

        user_data = UserCacheData(
            user_id=user_info.get("id"),
            telegram_id=telegram_id,
            name=user_info.get("name"),
            role=parse_user_role(user_info.get("role")),
            username=username,
            cached_at=now,
            access_token=response_data["access_token"],
            refresh_token=response_data["refresh_token"],
            token_expires_at=now + timedelta(seconds=expires_in),
            refresh_expires_at=now + timedelta(seconds=refresh_expires_in),
        )

        await self.storage.save_user_data(telegram_id, user_data, ttl=refresh_expires_in)

        logger.info(f"Данные пользователя {telegram_id} сохранены после login")

        user_dto = UserDTO(
            user_id=user_data.user_id,
            telegram_id=user_data.telegram_id,
            name=user_data.name,
            role=user_data.role,
        )
        return user_dto, user_data

    async def _create_guest(
        self, telegram_id: int, username: str | None
    ) -> tuple[UserDTO, UserCacheData]:
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
            cached_at=datetime.now(UTC),
        )

        # Сохраняем гостя в Redis с коротким TTL (5 минут)
        await self.storage.save_user_data(telegram_id, user_data, ttl=300)

        logger.debug(f"Создан гость для {telegram_id}")

        user_dto = UserDTO(
            user_id=None,
            telegram_id=telegram_id,
            name=None,
            role=UserRole.GUEST,
        )
        return user_dto, user_data


__all__ = ["UserDataFilter"]
