import asyncio
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from backend.src.core.config import get_bot_token, settings
from backend.src.core.logging import get_logger, setup_logging

from bot.auth import auth_router, generate_fernet_key
from bot.auth import protected_router as protected_auth_router
from bot.auth_middleware import AuthMiddleware
from bot.base_handlers import protected_router as protected_handlers_router
from bot.base_handlers import public_router
from bot.client_manager import client_manager
from bot.orders_handlers import orders_router
from bot.user_data_middleware import UserDataMiddleware

logger = get_logger(__name__)


def create_bot(**kwargs) -> Bot:
    """Создает экземпляр бота с токеном из конфигурации."""
    bot_token = get_bot_token()
    return Bot(token=bot_token, **kwargs)


def create_dispatcher(storage) -> Dispatcher:
    """
    Создает диспетчер с настроенными middleware и роутерами.
    """
    dp = Dispatcher(storage=storage)

    redis_client = storage.redis if isinstance(storage, RedisStorage) else None
    if redis_client:
        logger.info("✅ Redis client из хранилища будет использован для middleware.")

    encryption_key = generate_fernet_key()

    # 1. Глобальный middleware для подготовки данных
    dp.update.middleware(UserDataMiddleware(encryption_key=encryption_key))

    # 2. Middleware для защиты, который применяется ЛОКАЛЬНО
    auth_middleware = AuthMiddleware(
        auth_client=client_manager.auth, redis=redis_client, encryption_key=encryption_key
    )

    # Применяем защитный middleware только к защищенным роутерам
    protected_auth_router.message.middleware(auth_middleware)
    protected_auth_router.callback_query.middleware(auth_middleware)
    protected_handlers_router.message.middleware(auth_middleware)
    protected_handlers_router.callback_query.middleware(auth_middleware)

    # Сначала роутеры с конкретными командами, в конце - с общим обработчиком текста.
    dp.include_router(auth_router)
    dp.include_router(protected_auth_router)
    dp.include_router(protected_handlers_router)
    dp.include_router(public_router)
    dp.include_router(orders_router)

    return dp


@asynccontextmanager
async def lifespan():
    # ... (код этой функции не меняется)
    logger.info("🚀 Инициализация Telegram бота...")
    bot = None
    storage = None
    redis_connection = None
    try:
        if settings.redis.use_redis:
            redis_connection = aioredis.from_url(settings.redis.redis_url, health_check_interval=30)
            storage = RedisStorage(redis_connection)
            logger.info("✅ Хранилище состояний: Redis.")
        else:
            storage = MemoryStorage()
            logger.info("✅ Хранилище состояний: Memory.")
        bot = create_bot()
        dp = create_dispatcher(storage=storage)
        logger.info("🎉 Telegram бот успешно инициализирован!")
        yield bot, dp
    finally:
        logger.info("🔌 Завершение работы...")
        if redis_connection:
            await redis_connection.close()
            logger.info("✅ Redis соединение закрыто.")
        if bot and bot.session:
            await bot.session.close()
            logger.info("✅ Сессия бота закрыта.")


async def run_polling(skip_updates: bool = True):
    # ... (код этой функции не меняется)
    async with lifespan() as (bot, dp):
        logger.info("🔄 Запуск бота в режиме polling...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(
            bot,
            skip_updates=skip_updates,
            allowed_updates=dp.resolve_used_update_types(),
        )


def main():
    # ... (код этой функции не меняется)
    setup_logging()
    try:
        asyncio.run(run_polling(skip_updates=settings.telegram.skip_updates))
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Работа бота завершена.")
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка при запуске бота: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()
