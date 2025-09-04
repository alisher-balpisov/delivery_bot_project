import asyncio
import re
import sys
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from src.api.routes import api_router
from src.core.config import get_upload_dir, settings
from src.core.database import close_db, init_db
from src.core.logging import get_logger, setup_logging
from src.notifications.service import initialize_notification_service

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения
    """
    logger.info(f"🚀 Запуск {settings.app_name} v{settings.app_version}")
    logger.info(f"🔧 Режим: {settings.environment}")

    # Инициализация при старте
    try:
        # Инициализация базы данных
        # Инициализация сервиса уведомлений
        await initialize_notification_service(app)
        logger.info("✅ Сервис уведомлений инициализирована")

        logger.info("🎉 Приложение успешно запущено!")
        await init_db()
        logger.info("✅ База данных инициализирована")

        # Создание директорий для файлов
        get_upload_dir()
        logger.info("✅ Директории созданы")

        logger.info("🎉 Приложение успешно запущено!")

    except Exception as e:
        logger.error(f"❌ Ошибка при запуске приложения: {e}")
        raise

    yield

    # Очистка при завершении
    try:
        logger.info("🛑 Завершение работы приложения...")

        # Закрытие соединений
        await close_db()
        logger.info("✅ База данных отключена")

        logger.info("👋 Приложение завершено")

    except Exception as e:
        logger.error(f"❌ Ошибка при завершении приложения: {e}")


def create_app() -> FastAPI:
    """
    Создание и настройка FastAPI приложения
    """

    # Создание приложения
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        lifespan=lifespan,
    )

    # Настройка rate limiting
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Middleware для санитизации и валидации входных данных
    @app.middleware("http")
    async def sanitize_input(request: Request, call_next):
        # Паттерны для потенциально опасных данных
        dangerous_patterns = [
            r";\s*--",  # SQL комментарии
            r";\s*/\*",  # Начало SQL блока комментариев
            r"<\s*script",  # XSS script tags
            r"javascript\s*:",  # JavaScript URI
            r"on\w+\s*=",  # XSS event handlers
        ]

        try:
            # Получаем тело запроса если это POST/PUT/PATCH
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                body_str = body.decode("utf-8", errors="ignore")

                for pattern in dangerous_patterns:
                    if re.search(pattern, body_str, re.IGNORECASE):
                        logger.warning(f"🚨 Suspicious input detected in request: {request.url}")
                        raise HTTPException(
                            status_code=400,
                            detail="Invalid input detected. Request blocked for security reasons.",
                        )

            response = await call_next(request)
            return response

        except HTTPException:
            raise
        except Exception as e:
            # Если не HTTPException, пропускаем и логируем
            logger.error(f"Error in sanitize middleware: {e}")
            response = await call_next(request)
            return response

    # CORS middleware
    app.add_middleware(CORSMiddleware, **settings.middleware.cors_kwargs())

    # middleware для логирования запросов
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"{request.method} {request.url} - {response.status_code} - {process_time:.4f}s"
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"{request.method} {request.url} - ERROR: {type(e).__name__}: {e} - {process_time:.4f}s"
            )
            # Re-raise the exception to let FastAPI handle it properly
            raise

    # Подключение API роутеров
    app.include_router(api_router, prefix=settings.api_prefix)

    # Статические файлы (для загруженных фото)
    upload_dir = get_upload_dir()
    app.mount("/static", StaticFiles(directory=str(upload_dir)), name="static")

    # Root endpoint
    @app.get("/")
    async def root():
        """Корневой эндпоинт"""
        return {
            "message": f"Добро пожаловать в {settings.app_name}!",
            "version": settings.app_version,
            "docs": "/docs" if settings.docs_url else "Документация отключена",
        }

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

    return app


app = create_app()


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
async def run_api_only():
    """
    Запуск только API без бота (для отладки)
    """
    setup_logging()

    await init_db()

    # Создание упрощенного приложения без бота
    app = FastAPI(title=f"{settings.app_name} API Only")
    app.include_router(api_router, prefix=settings.api_prefix)

    config = uvicorn.Config(app, host=settings.api_host, port=settings.api_port)
    server = uvicorn.Server(config)

    try:
        logger.info("🔗 Запуск только API...")
        await server.serve()
    finally:
        await close_db()


# Команды для разработки
if __name__ == "__main__" and len(sys.argv) > 1:
    command = sys.argv[1]

    if command == "api":
        asyncio.run(run_api_only())
    elif command == "help":
        print("""
Команды для запуска:
  python main.py       - Запуск полного приложения (API + Bot)
  python main.py api   - Запуск только API
  python main.py help  - Показать эту справку
        """)
    else:
        print(f"❌ Неизвестная команда: {command}")
        print("Используйте 'python main.py help' для справки")
        sys.exit(1)
elif __name__ == "__main__":
    main()
