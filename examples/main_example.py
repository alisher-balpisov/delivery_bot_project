import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# Импорты API роутеров
from api.routes import api_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Импорты бота
from src.bot.main import create_bot, create_dispatcher
from src.bot.webhook import setup_webhook
from src.core.config import get_upload_dir, settings
from src.core.database import close_db, init_db
from src.core.logging import setup_logging
from src.core.redis import close_redis, init_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения
    """
    logger.info(f"🚀 Запуск {settings.app_name} v{settings.app_version}")
    logger.info(f"🔧 Режим: {settings.environment}")

    # Инициализация при старте
    try:
        app.state.background_tasks = set()  # Initialize set for background tasks
        # Валидация конфигурации
        logger.info("✅ Конфигурация валидна")

        # Инициализация базы данных
        await init_db()
        logger.info("✅ База данных инициализирована")

        # Инициализация Redis
        await init_redis()
        logger.info("✅ Redis инициализирован")

        # Создание директорий для файлов
        get_upload_dir()
        logger.info("✅ Директории созданы")

        # Инициализация бота
        bot = create_bot()
        dp = create_dispatcher()

        # Настройка webhook или polling
        if settings.telegram.use_webhook:
            await setup_webhook(bot)
            logger.info("✅ Webhook настроен")
        else:
            # Запуск polling в фоновой задаче
            polling_task = asyncio.create_task(start_polling(bot, dp))
            app.state.background_tasks.add(polling_task)  # Store the task
            polling_task.add_done_callback(app.state.background_tasks.discard)  # Remove when done
            logger.info("✅ Polling запущен")

        # Сохранение экземпляров в app.state для доступа из других частей
        app.state.bot = bot
        app.state.dispatcher = dp

        logger.info("🎉 Приложение успешно запущено!")

    except Exception as e:
        logger.error(f"❌ Ошибка при запуске приложения: {e}")
        raise

    yield

    # Очистка при завершении
    try:
        logger.info("🛑 Завершение работы приложения...")

        # Отмена фоновых задач
        for task in list(app.state.background_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("✅ Фоновые задачи отменены")

        # Закрытие соединений
        if hasattr(app.state, "bot"):
            await app.state.bot.session.close()
            logger.info("✅ Telegram Bot сессия закрыта")

        await close_redis()
        logger.info("✅ Redis соединение закрыто")

        await close_db()
        logger.info("✅ База данных отключена")

        logger.info("👋 Приложение завершено")

    except Exception as e:
        logger.error(f"❌ Ошибка при завершении приложения: {e}")


async def start_polling(bot: Bot, dp: Dispatcher):
    """
    Запуск бота в режиме polling (для разработки)
    """
    try:
        logger.info("🔄 Запуск polling...")
        await dp.start_polling(
            bot,
            skip_updates=True,  # Пропустить накопившиеся обновления
            allowed_updates=dp.resolve_used_update_types(),
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в polling: {e}")
        raise


def create_app() -> FastAPI:
    """
    Создание и настройка FastAPI приложения
    """

    # Создание приложения
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API для координации работы между магазинами и курьерами",
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        lifespan=lifespan,
    )

    # CORS middleware
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
        )

    # Подключение API роутеров
    app.include_router(api_router, prefix=settings.api_prefix)

    # Статические файлы (для загруженных фото)
    upload_dir = get_upload_dir()
    app.mount("/static", StaticFiles(directory=str(upload_dir)), name="static")

    # Webhook для Telegram бота (если используется)
    if settings.telegram.use_webhook:
        webhook_handler = SimpleRequestHandler(
            dispatcher=create_dispatcher(),
            bot=create_bot(),
        )
        webhook_handler.register(app, path=settings.telegram.webhook_path)

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Проверка здоровья приложения"""
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    # Root endpoint
    @app.get("/")
    async def root():
        """Корневой эндпоинт"""
        return {
            "message": f"Добро пожаловать в {settings.app_name}!",
            "version": settings.app_version,
            "docs": "/docs" if settings.docs_url else "Документация отключена",
            "health": "/health",
        }

    return app


async def run_app():
    """
    Запуск приложения
    """
    try:
        # Настройка логирования
        setup_logging()

        # Создание приложения
        app = create_app()

        # Настройка uvicorn
        config = uvicorn.Config(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level=settings.logging.level.lower(),
            access_log=settings.debug,
            reload=settings.debug and settings.is_development,
        )

        # Запуск сервера
        server = uvicorn.Server(config)

        logger.info(f"🌐 Сервер запускается на http://{settings.api_host}:{settings.api_port}")

        if settings.debug:
            logger.info(
                f"📚 Документация доступна на http://{settings.api_host}:{settings.api_port}/docs"
            )

        await server.serve()

    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал завершения")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)


def main():
    """
    Основная функция для запуска через CLI
    """
    try:
        # Запуск приложения
        asyncio.run(run_app())

    except KeyboardInterrupt:
        print("\n👋 Работа завершена пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка при запуске: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


# Дополнительные функции для разработки и отладки


async def run_bot_only():
    """
    Запуск только бота без API (для отладки)
    """
    setup_logging()

    await init_db()
    await init_redis()

    bot = create_bot()
    dp = create_dispatcher()

    try:
        logger.info("🤖 Запуск только Telegram бота...")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()
        await close_redis()
        await close_db()


async def run_api_only():
    """
    Запуск только API без бота (для отладки)
    """
    setup_logging()

    await init_db()
    await init_redis()

    # Создание упрощенного приложения без бота
    app = FastAPI(title=f"{settings.app_name} API Only")
    app.include_router(api_router, prefix=settings.api_prefix)

    config = uvicorn.Config(app, host=settings.api_host, port=settings.api_port)
    server = uvicorn.Server(config)

    try:
        logger.info("🔗 Запуск только API...")
        await server.serve()
    finally:
        await close_redis()
        await close_db()


# Команды для разработки
if __name__ == "__main__" and len(sys.argv) > 1:
    command = sys.argv[1]

    if command == "bot":
        asyncio.run(run_bot_only())
    elif command == "api":
        asyncio.run(run_api_only())
    elif command == "help":
        print("""
Команды для запуска:
  python main.py       - Запуск полного приложения (API + Bot)
  python main.py bot   - Запуск только бота
  python main.py api   - Запуск только API
  python main.py help  - Показать эту справку
        """)
    else:
        print(f"❌ Неизвестная команда: {command}")
        print("Используйте 'python main.py help' для справки")
        sys.exit(1)
elif __name__ == "__main__":
    main()
