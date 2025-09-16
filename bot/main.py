import asyncio
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types.error_event import ErrorEvent
from backend.src.core.config import get_bot_token, settings
from backend.src.core.logging import get_logger, setup_logging

from bot.handlers import *
from bot.middlewares.user_data_middleware import UserDataMiddleware

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

    # 1. Глобальный middleware для подготовки данных
    dp.update.middleware(UserDataMiddleware())

    # Порядок регистрации роутеров важен!
    # Сначала идут роутеры с более конкретными фильтрами (команды, состояния).
    dp.include_router(auth_router)
    dp.include_router(orders_router)
    dp.include_router(protected_router)

    # Роутер с "catch-all" обработчиком (F.text) должен быть последним.
    dp.include_router(public_router)

    async def on_unknown_error(event: ErrorEvent):
        logger.critical(f"Критическая ошибка: {event.exception}", exc_info=True)
        # Можно попытаться уведомить пользователя, если это возможно
        if event.update and event.update.message:
            await event.update.message.answer(
                "Произошла непредвиденная ошибка. Мы уже работаем над этим."
            )

    dp.errors.register(on_unknown_error)

    return dp


@asynccontextmanager
async def lifespan():
    # ... (код этой функции не меняется)
    logger.info("🚀 Инициализация Telegram бота...")
    bot = None
    try:
        storage = MemoryStorage()
        logger.info("✅ Хранилище состояний: Memory.")
        bot = create_bot()
        dp = create_dispatcher(storage=storage)
        logger.info("🎉 Telegram бот успешно инициализирован!")
        yield bot, dp
    finally:
        logger.info("🔌 Завершение работы...")
        if bot and bot.session:
            await bot.session.close()
            logger.info("✅ Сессия бота закрыта.")


async def run_polling(skip_updates: bool = True):
    # ... (код этой функции не меняется)
    async with lifespan() as (bot, dp):
        logger.info("🔄 Запуск бота в режиме polling...")

        # Попытка удалить webhook с обработкой ошибок сети
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
