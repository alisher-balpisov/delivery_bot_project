import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as redis
from backend.src.common.enums import UserRole
from backend.src.core.config import RedisConfig
from backend.src.core.logging import get_logger
from redis.asyncio import Redis

logger = get_logger(__name__)


@dataclass
class UserCacheData:
    """Кэшируемые данные пользователя"""

    user_id: int | None
    telegram_id: int
    name: str | None
    role: UserRole
    username: str | None = None
    # Токены
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    # Метаданные
    last_activity: datetime | None = None
    cached_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Сериализация для Redis"""
        data = asdict(self)
        # Преобразуем enum и datetime в нужные форматы
        data["role"] = self.role.value
        if self.token_expires_at:
            data["token_expires_at"] = self.token_expires_at.timestamp()
        if self.refresh_expires_at:
            data["refresh_expires_at"] = self.refresh_expires_at.timestamp()
        if self.last_activity:
            data["last_activity"] = self.last_activity.isoformat()
        if self.cached_at:
            data["cached_at"] = self.cached_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserCacheData":
        """Десериализация из Redis"""
        # Восстанавливаем enum и datetime
        data["role"] = UserRole(data["role"])
        if data.get("token_expires_at") is not None:
            data["token_expires_at"] = datetime.fromtimestamp(data["token_expires_at"], tz=UTC)
        if data.get("refresh_expires_at") is not None:
            data["refresh_expires_at"] = datetime.fromtimestamp(data["refresh_expires_at"], tz=UTC)
        if data.get("last_activity"):
            data["last_activity"] = datetime.fromisoformat(data["last_activity"])
        if data.get("cached_at"):
            data["cached_at"] = datetime.fromisoformat(data["cached_at"])
        return cls(**data)

    @property
    def has_valid_token(self) -> bool:
        """Проверяет наличие валидного токена"""
        if not self.access_token or not self.token_expires_at:
            return False
        return datetime.now(UTC) < self.token_expires_at

    @property
    def needs_token_refresh(self) -> bool:
        """Проверяет необходимость обновления токена (за 5 минут до истечения)"""
        if not self.token_expires_at:
            return False
        return datetime.now(UTC) >= self.token_expires_at - timedelta(minutes=5)

    @property
    def refresh_token_valid(self) -> bool:
        """Проверяет валидность refresh токена"""
        if not self.refresh_token or not self.refresh_expires_at:
            return False
        return datetime.now(UTC) < self.refresh_expires_at


class UserDataStorage:
    """
    Централизованное хранилище данных пользователя в Redis.

    Ключевые особенности:
    - Единое место хранения всех данных пользователя
    - Автоматическое управление TTL
    - Кэширование профиля для снижения нагрузки на API
    """

    # Префиксы для ключей Redis
    USER_DATA_PREFIX = "user_data"
    PROFILE_CACHE_PREFIX = "profile_cache"

    # TTL по умолчанию
    DEFAULT_TTL = 3600  # 1 час
    PROFILE_CACHE_TTL = 300  # 5 минут для кэша профиля

    def __init__(self, config: RedisConfig):
        self.config = config
        self.redis_client: Redis | None = None

    async def get_redis_client(self) -> Redis:
        """Получает или создает Redis клиент"""
        if self.redis_client is None:
            self.redis_client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                decode_responses=True,
            )
        return self.redis_client

    def _make_user_key(self, telegram_id: int) -> str:
        """Создает ключ для данных пользователя"""
        return f"{self.USER_DATA_PREFIX}:{telegram_id}"

    def _make_profile_key(self, telegram_id: int) -> str:
        """Создает ключ для кэша профиля"""
        return f"{self.PROFILE_CACHE_PREFIX}:{telegram_id}"

    # === Основные методы работы с данными пользователя ===

    async def get_user_data(self, telegram_id: int) -> UserCacheData | None:
        """
        Получает полные данные пользователя из Redis.

        Returns:
            UserCacheData или None если данных нет
        """
        try:
            client = await self.get_redis_client()
            key = self._make_user_key(telegram_id)
            data = await client.get(key)

            if not data:
                logger.debug(f"Данные пользователя {telegram_id} не найдены в Redis")
                return None

            return UserCacheData.from_dict(json.loads(data))

        except Exception as e:
            logger.error(f"Ошибка получения данных пользователя {telegram_id}: {e}", exc_info=True)
            return None

    async def save_user_data(
        self, telegram_id: int, user_data: UserCacheData, ttl: int | None = None
    ) -> bool:
        """
        Сохраняет полные данные пользователя в Redis.

        Args:
            telegram_id: Telegram ID пользователя
            user_data: Данные для сохранения
            ttl: Время жизни в секундах (по умолчанию DEFAULT_TTL)

        Returns:
            True при успехе, False при ошибке
        """
        try:
            client = await self.get_redis_client()
            key = self._make_user_key(telegram_id)

            # Обновляем метаданные
            if user_data.cached_at is None:
                user_data.cached_at = datetime.now(UTC)
            user_data.last_activity = datetime.now(UTC)

            # Сохраняем с TTL
            ttl = ttl or self.DEFAULT_TTL
            await client.setex(key, ttl, json.dumps(user_data.to_dict()))

            logger.debug(f"Данные пользователя {telegram_id} сохранены в Redis")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения данных пользователя {telegram_id}: {e}", exc_info=True)
            return False

    async def update_user_data(
        self, telegram_id: int, updates: dict[str, Any], ttl: int | None = None
    ) -> bool:
        """
        Частично обновляет данные пользователя.

        Args:
            telegram_id: Telegram ID пользователя
            updates: Словарь с обновлениями
            ttl: Новое время жизни (по умолчанию сохраняется старое)

        Returns:
            True при успехе, False при ошибке
        """
        try:
            # Получаем текущие данные
            current_data = await self.get_user_data(telegram_id)

            if current_data is None:
                logger.warning(f"Попытка обновления несуществующих данных для {telegram_id}")
                return False

            # Обновляем поля
            data_dict = current_data.to_dict()
            data_dict.update(updates)

            # Создаем обновленный объект
            updated_data = UserCacheData.from_dict(data_dict)

            # Сохраняем
            return await self.save_user_data(telegram_id, updated_data, ttl)

        except Exception as e:
            logger.error(f"Ошибка обновления данных пользователя {telegram_id}: {e}", exc_info=True)
            return False

    async def delete_user_data(self, telegram_id: int) -> bool:
        """
        Удаляет все данные пользователя из Redis.

        Returns:
            True при успехе
        """
        try:
            client = await self.get_redis_client()
            user_key = self._make_user_key(telegram_id)
            profile_key = self._make_profile_key(telegram_id)

            await client.delete(user_key, profile_key)
            logger.info(f"Данные пользователя {telegram_id} удалены из Redis")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления данных пользователя {telegram_id}: {e}", exc_info=True)
            return False

    # === Методы работы с токенами ===

    async def save_tokens(
        self,
        telegram_id: int,
        access_token: str,
        refresh_token: str,
        access_expires_in: int,
        refresh_expires_in: int,
    ) -> bool:
        """Сохраняет токены пользователя."""
        now = datetime.now(UTC)
        updates = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": (now + timedelta(seconds=access_expires_in)).timestamp(),
            "refresh_expires_at": (now + timedelta(seconds=refresh_expires_in)).timestamp(),
        }
        return await self.update_user_data(telegram_id, updates, ttl=refresh_expires_in)

    async def update_activity_optimized(self, telegram_id: int, ttl: int | None = None) -> bool:
        """Продлевает время жизни ключа без переписывания данных."""
        try:
            client = await self.get_redis_client()
            key = self._make_user_key(telegram_id)
            await client.expire(key, ttl or self.DEFAULT_TTL)
            return True
        except Exception:
            return False

    async def get_access_token(self, telegram_id: int) -> str | None:
        """Получает access токен пользователя если он валиден"""
        user_data = await self.get_user_data(telegram_id)

        if not user_data or not user_data.has_valid_token:
            return None

        return user_data.access_token

    async def invalidate_tokens(self, telegram_id: int) -> bool:
        """Инвалидирует токены пользователя"""
        updates = {
            "access_token": None,
            "refresh_token": None,
            "token_expires_at": None,
            "refresh_expires_at": None,
        }

        return await self.update_user_data(telegram_id, updates)

    # === Методы работы с кэшем профиля ===

    async def cache_profile(self, telegram_id: int, profile_data: dict[str, Any]) -> bool:
        """
        Кэширует данные профиля пользователя из API.

        Используется для снижения количества запросов к API.
        """
        try:
            client = await self.get_redis_client()
            key = self._make_profile_key(telegram_id)

            profile_data["cached_at"] = datetime.now(UTC).isoformat()

            await client.setex(key, self.PROFILE_CACHE_TTL, json.dumps(profile_data))

            logger.debug(f"Профиль пользователя {telegram_id} кэширован")
            return True

        except Exception as e:
            logger.error(f"Ошибка кэширования профиля {telegram_id}: {e}", exc_info=True)
            return False

    async def get_cached_profile(self, telegram_id: int) -> dict[str, Any] | None:
        """
        Получает кэшированный профиль пользователя.

        Returns:
            Данные профиля или None если кэш истек
        """
        try:
            client = await self.get_redis_client()
            key = self._make_profile_key(telegram_id)

            data = await client.get(key)
            if not data:
                return None

            profile = json.loads(data)
            logger.debug(f"Профиль пользователя {telegram_id} получен из кэша")
            return profile

        except Exception as e:
            logger.error(f"Ошибка получения кэша профиля {telegram_id}: {e}", exc_info=True)
            return None

    # === Вспомогательные методы ===

    async def update_activity(self, telegram_id: int, ttl: int | None = None) -> bool:
        """Обновляет время последней активности пользователя"""
        return await self.update_user_data(
            telegram_id, {"last_activity": datetime.now(UTC).isoformat()}, ttl=ttl
        )

    async def get_field(self, telegram_id: int, field: str) -> Any:
        """Получает конкретное поле из данных пользователя"""
        user_data = await self.get_user_data(telegram_id)
        if not user_data:
            return None

        return getattr(user_data, field, None)

    async def close(self) -> None:
        """Закрывает соединение с Redis"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis соединение закрыто")


__all__ = ["UserCacheData", "UserDataStorage"]
