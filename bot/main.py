import asyncio
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types.error_event import ErrorEvent
from backend.src.core.config import get_bot_token, settings
from backend.src.core.logging import get_logger, setup_logging

from bot.clients import ClientManager
from bot.clients.base_client import ConnectionPool
from bot.filters.user_data_filter import UserDataFilter
from bot.handlers import *

logger = get_logger(__name__)


def create_bot(**kwargs) -> Bot:
    """Создает экземпляр бота."""
    return Bot(token=get_bot_token(), **kwargs)


def create_dispatcher(storage, **kwargs) -> Dispatcher:
    """Создает и настраивает диспетчер."""
    dp = Dispatcher(storage=storage, **kwargs)

    # UserDataFilter теперь нуждается в клиентах для выполнения
    # поиска токенов/пользователей. Мы передаем эти клиенты напрямую в его конструктор.
    # Aiogram будет использовать эти экземпляры при срабатывании фильтра.
    user_data_provider = UserDataFilter()

    # Применяем фильтр ко всем роутерам, которые обрабатывают взаимодействия с пользователем.
    for router in [auth_router, protected_router, orders_router, public_router]:
        router.message.filter(user_data_provider)
        router.callback_query.filter(user_data_provider)

    dp.include_router(auth_router)
    dp.include_router(protected_router)
    dp.include_router(orders_router)
    dp.include_router(public_router)

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
    """Асинхронный менеджер контекста для жизненного цикла приложения."""
    logger.info("🚀 Инициализация Telegram бота...")
    bot = None
    pool = ConnectionPool()
    try:
        storage = MemoryStorage()
        logger.info("✅ Хранилище состояний: Memory.")
        client_manager = ClientManager(pool=pool)
        bot = create_bot()

        # Передаем все клиенты как именованные аргументы в диспетчер.
        # Они будут доступны в обработчиках и, что важно, в фильтрах.
        dp = create_dispatcher(
            storage=storage,
            admin_client=client_manager.admin,
            auth_client=client_manager.auth,
            disputes_client=client_manager.disputes,
            notifications_client=client_manager.notifications,
            orders_client=client_manager.orders,
            system_client=client_manager.system,
            users_client=client_manager.users,
        )

        logger.info("🎉 Telegram бот успешно инициализирован!")
        yield bot, dp
    finally:
        logger.info("🔌 Завершение работы...")
        await pool.close()
        if bot and bot.session:
            await bot.session.close()
            logger.info("✅ Сессия бота закрыта.")


async def run_polling(skip_updates: bool = True):
    """Запускает бота в режиме опроса."""
    async with lifespan() as (bot, dp):
        logger.info("🔄 Запуск бота в режиме polling...")
        try:
            await bot.delete_webhook(drop_pending_updates=True, request_timeout=60)
            logger.info("✅ Webhook успешно удален")
        except TelegramNetworkError as e:
            logger.warning(f"⚠️ Не удалось удалить webhook: {e}. Продолжаем без удаления.")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при удалении webhook: {e}. Продолжаем без удаления.")
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
