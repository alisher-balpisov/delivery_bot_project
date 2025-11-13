import asyncio
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types.error_event import ErrorEvent
from backend.src.core.config import get_bot_token, settings
from backend.src.core.logging import get_logger, setup_logging

from bot.clients import ClientManager
from bot.clients.base_client import ConnectionPool
from bot.filters.user_data_filter import UserDataFilter
from bot.handlers import *
from bot.middleware import setup_middlewares
from bot.middleware.token_refresh_middleware import TokenRefreshMiddleware
from bot.redis_storage import UserDataStorage

logger = get_logger(__name__)


def create_bot(**kwargs) -> Bot:
    """Создает экземпляр бота."""
    return Bot(token=get_bot_token(), **kwargs)


def create_dispatcher(
    storage, user_data_storage: UserDataStorage, client_manager: ClientManager, **kwargs
) -> Dispatcher:
    """
    Создает и настраивает диспетчер.

    Изменения:
    - UserDataStorage передается явно
    - ClientManager передается для доступа к клиентам
    - TokenRefreshMiddleware регистрируется после setup_middlewares
    """
    dp = Dispatcher(storage=storage, **kwargs)

    # Регистрируем middleware ДО фильтров и роутеров
    setup_middlewares(dp)

    # Регистрируем middleware для обновления токенов
    token_refresh_middleware = TokenRefreshMiddleware(
        storage=user_data_storage,
        auth_client=client_manager.auth,
    )
    # Регистрируем middleware для message и callback_query
    dp.message.middleware(token_refresh_middleware)
    dp.callback_query.middleware(token_refresh_middleware)

    # Сохраняем middleware в kwargs для доступа в lifespan
    kwargs["token_refresh_middleware"] = token_refresh_middleware

    # Создаем фильтр с UserDataStorage
    user_data_provider = UserDataFilter(user_data_storage)

    # Применяем фильтр ко всем роутерам
    for router in [auth_router, protected_router, orders_router, public_router]:
        router.message.filter(user_data_provider)
        router.callback_query.filter(user_data_provider)
    # Регистрируем роутеры
    dp.include_router(auth_router)
    dp.include_router(protected_router)
    dp.include_router(orders_router)
    dp.include_router(public_router)

    # Обработчик критических ошибок
    async def on_unknown_error(event: ErrorEvent):
        logger.critical(f"Критическая ошибка: {event.exception}", exc_info=True)
        if event.update and event.update.message:
            await event.update.message.answer(
                "Произошла непредвиденная ошибка. Мы уже работаем над этим."
            )

    dp.errors.register(on_unknown_error)

    return dp


@asynccontextmanager
async def lifespan():
    """
    Асинхронный менеджер контекста для жизненного цикла приложения.
    """
    logger.info("🚀 Инициализация Telegram бота...")
    bot = None
    pool = ConnectionPool()
    user_data_storage = None
    token_refresh_middleware = None

    try:
        # 1. Создаем хранилище для FSM
        storage = MemoryStorage()
        logger.info("✅ Хранилище FSM: Memory")

        # 2. Создаем хранилище данных пользователей (Redis)
        user_data_storage = UserDataStorage(settings.redis)
        logger.info("✅ Хранилище данных пользователей: Redis")

        # 3. Создаем менеджер клиентов API
        client_manager = ClientManager(pool=pool)
        logger.info("✅ API клиенты инициализированы")

        # 4. Создаем бота
        bot = create_bot()
        logger.info("✅ Бот создан")

        # 5. Создаем диспетчер с передачей всех зависимостей
        dp_kwargs = {
            "storage": storage,
            "user_data_storage": user_data_storage,
            "client_manager": client_manager,
            # Передаем клиенты как kwargs для доступа в хендлерах
            "admin_client": client_manager.admin,
            "auth_client": client_manager.auth,
            "disputes_client": client_manager.disputes,
            "notifications_client": client_manager.notifications,
            "orders_client": client_manager.orders,
            "system_client": client_manager.system,
            "users_client": client_manager.users,
            "user_storage": user_data_storage,  # Передаем storage для TokenManager с другим именем
        }
        dp = create_dispatcher(**dp_kwargs)
        logger.info("✅ Диспетчер настроен")

        # 6. Запускаем cleanup задачу для TokenRefreshMiddleware
        token_refresh_middleware = dp_kwargs.get("token_refresh_middleware")
        if token_refresh_middleware:
            await token_refresh_middleware.start_cleanup_task()
            logger.info("✅ Задача очистки locks запущена")

        logger.info("🎉 Telegram бот успешно инициализирован!")

        try:
            yield bot, dp
        finally:
            # Останавливаем cleanup задачу
            if token_refresh_middleware:
                await token_refresh_middleware.stop_cleanup_task()
                logger.info("✅ Задача очистки locks остановлена")

    finally:
        logger.info("🔌 Завершение работы...")

        # Закрываем Redis соединение
        if user_data_storage:
            await user_data_storage.close()
            logger.info("✅ Redis соединение закрыто")

        # Закрываем HTTP клиент
        await pool.close()
        logger.info("✅ HTTP соединения закрыты")

        # Закрываем сессию бота
        if bot and bot.session:
            await bot.session.close()
            logger.info("✅ Сессия бота закрыта")


async def run_polling(skip_updates: bool = True):
    """Запускает бота в режиме опроса."""
    async with lifespan() as (bot, dp):
        logger.info("🔄 Запуск бота в режиме polling...")

        await dp.start_polling(
            bot,
            skip_updates=skip_updates,
            allowed_updates=dp.resolve_used_update_types(),
        )


def main():
    """Основная функция для запуска бота."""
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
