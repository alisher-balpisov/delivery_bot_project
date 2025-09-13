import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from backend.src.common.enums import UserRole
from backend.src.core.config import settings
from backend.src.core.logging import get_logger
from cryptography.fernet import Fernet
from redis.asyncio import Redis
from redis.exceptions import RedisError

from bot.clients.auth_client import AuthClient
from bot.constants import ErrorMessages

logger = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки авторизации на защищенных роутах."""

    def __init__(
        self,
        auth_client: AuthClient,
        redis: Redis | None = None,
        encryption_key: str | None = None,
        rate_limit: int = 10,
        cache_ttl: int = 300,
    ):
        self.auth_client = auth_client
        self.redis = redis
        self.rate_limit = rate_limit
        self.fernet = Fernet(encryption_key.encode()) if encryption_key else None
        self.cache_ttl = cache_ttl

        if settings.is_production and not encryption_key:
            raise ValueError("В production среде encryption_key обязателен")

    def _encrypt_token(self, token: str) -> str:
        if self.fernet:
            return self.fernet.encrypt(token.encode()).decode()
        return token

    async def _check_rate_limit(self, telegram_id: int, user_role: str | None) -> tuple[bool, int]:
        if user_role == UserRole.ADMIN:
            return True, 0
        if not self.redis:
            return True, 0

        key = f"ratelimit:user:{telegram_id}"
        now = int(time.time())
        window_start = now - 60

        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, "-inf", window_start)
                pipe.zcard(key)
                pipe.zrange(key, 0, 0, withscores=True)
                results = await pipe.execute()

            count = results[1]
            if count >= self.rate_limit:
                first_request = results[2]
                if first_request:
                    reset_time = int(first_request[0][1]) + 60 - now
                    return False, max(0, reset_time)

            await self.redis.zadd(key, {f"{now}": now})
            await self.redis.expire(key, 120)
            return True, 0

        except RedisError as e:
            logger.error(f"Redis error in rate limit: {e}")
            return True, 0

    async def _validate_token_cached(self, token: str, telegram_id: int) -> dict | None:
        # 1. Попробовать достать из кэша Redis
        if self.redis:
            cache_key = f"token_cache:{telegram_id}"
            try:
                cached_data = await self.redis.get(cache_key)
                if cached_data:
                    logger.debug(f"Token for user {telegram_id} found in Redis cache.")
                    return json.loads(cached_data)
            except RedisError as e:
                logger.error(f"Redis error when getting token cache: {e}")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to decode token cache for user {telegram_id}.")

        # 2. Если в кэше нет - валидировать через API
        validated = await self.auth_client.validate_token(token)

        # 3. Если валидация успешна - сохранить в кэш Redis
        if validated and self.redis:
            try:
                await self.redis.set(
                    cache_key, json.dumps(validated), ex=self.cache_ttl
                )
                logger.debug(f"Token for user {telegram_id} saved to Redis cache.")
            except RedisError as e:
                logger.error(f"Redis error when setting token cache: {e}")

        return validated

    async def _set_user_data(self, data: dict[str, Any], user_data: dict[str, Any]):
        state = data.get("state")
        if not state:
            return

        data_to_store = user_data.copy()

        try:
            # Логика шифрования остается прежней
            if "access_token" in data_to_store and self.fernet:
                data_to_store["access_token_encrypted"] = self._encrypt_token(
                    data_to_store["access_token"]
                )
                del data_to_store["access_token"]

            await state.update_data(data_to_store)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных FSM: {e}")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        user_data: dict = data["user_data"]  # <-- Теперь мы просто берем его из data

        # Rate Limiter
        allowed, reset_time = await self._check_rate_limit(user.id, user_data.get("role"))
        if not allowed:
            if hasattr(event, "answer"):
                await event.answer(f"🚫 Слишком много запросов! Повторите через {reset_time} сек.")
            return

        # Проверка токена
        token = user_data.get("access_token")
        if not token:
            if hasattr(event, "answer"):
                await event.answer(ErrorMessages.Auth.UNAUTHORIZED)
                return

        validated = await self._validate_token_cached(token, user.id)
        if not validated:
            if hasattr(event, "answer"):
                await event.answer(ErrorMessages.Auth.INVALID_TOKEN)
                if data.get("state"):
                    await data["state"].clear()
                return

        # Обновляем данные в state и в data для следующих middlewares/хендлеров
        await self._set_user_data(data, validated)
        data["user_data"] = validated

        return await handler(event, data)
