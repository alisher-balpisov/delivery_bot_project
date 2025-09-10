# Файл: bot/auth_middleware.py (ЗАМЕНИТЬ)

"""
Middleware для ЗАЩИТЫ роутов. Проверяет наличие валидного токена.
Предполагает, что UserDataMiddleware уже отработал.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from backend.src.core.logging import get_logger
from cryptography.fernet import Fernet
from redis.asyncio import Redis
from redis.exceptions import RedisError

from bot.auth_client import AuthClient

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
        self.token_cache: dict[int, dict[str, Any]] = {}

    def _encrypt_token(self, token: str) -> str:
        if self.fernet:
            return self.fernet.encrypt(token.encode()).decode()
        return token

    async def _check_rate_limit(self, telegram_id: int, user_role: str | None) -> tuple[bool, int]:
        # ... (код этой функции не меняется)
        if user_role == "admin":
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
                    logger.warning(f"Rate limit превышен для пользователя {telegram_id}")
                    return False, max(0, reset_time)
            await self.redis.zadd(key, {f"{now}": now})
            await self.redis.expire(key, 120)
            return True, 0
        except RedisError as e:
            logger.error(f"Ошибка Redis при проверке rate limit для {telegram_id}: {e}")
            return True, 0

    async def _validate_token_cached(self, token: str, telegram_id: int) -> dict | None:
        # ... (код этой функции не меняется)
        cached = self.token_cache.get(telegram_id)
        if cached and cached.get("expires_at", 0) > time.time():
            return cached
        validated = await self.auth_client.validate_token(token)
        if validated:
            validated["expires_at"] = time.time() + self.cache_ttl
            self.token_cache[telegram_id] = validated
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
                await event.answer("❌ Сначала авторизуйтесь с помощью /start")
            return

        validated = await self._validate_token_cached(token, user.id)
        if not validated:
            if hasattr(event, "answer"):
                await event.answer("❌ Токен недействителен. Авторизуйтесь заново: /start")
            if data.get("state"):
                await data["state"].clear()
            return

        # Обновляем данные в state и в data для следующих middlewares/хендлеров
        await self._set_user_data(data, validated)
        data["user_data"] = validated

        return await handler(event, data)
