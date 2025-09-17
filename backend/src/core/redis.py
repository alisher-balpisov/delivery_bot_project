from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from backend.src.core.config import settings
from backend.src.core.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Менеджер для управления пулом соединений Redis."""

    def __init__(self):
        self._pool = None

    async def init_redis(self):
        """Инициализация пула соединений Redis."""
        try:
            password = (
                settings.redis.password.get_secret_value() if settings.redis.password else None
            )
            self._pool = aioredis.ConnectionPool.from_url(
                f"redis://{settings.redis.host}:{settings.redis.port}/{settings.redis.db}",
                password=password,
                max_connections=20,
                decode_responses=True,  # Важно для работы со строками
            )
            logger.info("✅ Пул соединений Redis успешно инициализирован")
        except Exception as e:
            logger.critical(f"❌ Не удалось инициализировать Redis: {e}", exc_info=True)
            raise

    async def close_redis(self):
        """Закрытие пула соединений Redis."""
        if self._pool:
            await self._pool.disconnect()
            logger.info("✅ Пул соединений Redis закрыт")

    def get_client(self) -> aioredis.Redis:
        """Получение клиента Redis из пула."""
        if not self._pool:
            raise RuntimeError(
                "Пул соединений Redis не был инициализирован. Вызовите init_redis() при старте."
            )
        return aioredis.Redis(connection_pool=self._pool)


# Глобальный экземпляр
redis_manager = RedisClient()


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Зависимость FastAPI для получения клиента Redis."""
    yield redis_manager.get_client()
