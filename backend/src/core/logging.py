import logging
import logging.handlers
import sys
from pathlib import Path
from typing import ClassVar

from backend.src.core.config import settings


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для консоли
    """

    # Цветовые коды ANSI
    COLORS: ClassVar = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record):
        # Добавляем цвет к уровню логирования
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"

        return super().format(record)


class TelegramFormatter(logging.Formatter):
    """
    Специальный форматтер для логов Telegram бота
    """

    def format(self, record):
        # Добавляем эмодзи для разных уровней
        emoji_map = {"DEBUG": "🐛", "INFO": "📋", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}

        emoji = emoji_map.get(record.levelname, "📋")
        record.emoji = emoji

        return super().format(record)


def setup_console_handler() -> logging.Handler:
    """
    Настройка обработчика для вывода в консоль
    """
    from backend.src.core.config import settings  # Lazy import to avoid circular dependency

    console_handler = logging.StreamHandler(sys.stdout)

    if settings.debug and sys.stdout.isatty():
        # Цветной вывод для терминала в режиме разработки
        formatter = ColoredFormatter(
            fmt=settings.logging.format, datefmt=settings.logging.date_format, style="{"
        )
    else:
        # Обычный вывод для продакшена или файлов
        formatter = logging.Formatter(
            fmt=settings.logging.format, datefmt=settings.logging.date_format, style="{"
        )

    console_handler.setFormatter(formatter)
    console_handler.setLevel(settings.logging.level)

    return console_handler


def setup_file_handler() -> logging.Handler | None:
    """
    Настройка обработчика для записи в файл
    """
    if not settings.logging.file_path:
        return None

    # Создаем директорию для логов если не существует
    log_file = Path(settings.logging.file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Используем RotatingFileHandler для ротации логов
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file), **settings.logging.handler_kwargs()
    )

    # Подробный формат для файловых логов
    formatter = logging.Formatter(
        fmt=settings.logging.file_format, datefmt=settings.logging.date_format, style="{"
    )

    file_handler.setFormatter(formatter)
    file_handler.setLevel(settings.logging.level)

    return file_handler


def setup_telegram_handler() -> logging.Handler:
    """
    Настройка специального обработчика для логов Telegram бота
    """
    # Создаем отдельный файл для логов бота если указан основной файл логов
    if settings.logging.file_path:
        bot_log_file = Path(settings.logging.file_path).parent / "telegram_bot.log"

        bot_handler = logging.handlers.RotatingFileHandler(
            filename=str(bot_log_file), **settings.logging.handler_kwargs()
        )

        formatter = TelegramFormatter(
            fmt=settings.logging.telegram_format, datefmt=settings.logging.date_format, style="{"
        )

        bot_handler.setFormatter(formatter)
        bot_handler.setLevel(settings.logging.level)

        return bot_handler

    return None


def setup_error_handler() -> logging.Handler | None:
    """
    Отдельный обработчик только для ошибок (ERROR и CRITICAL)
    """
    if not settings.logging.file_path:
        return None

    error_log_file = Path(settings.logging.file_path).parent / "errors.log"

    error_handler = logging.handlers.RotatingFileHandler(
        filename=str(error_log_file), **settings.logging.handler_kwargs()
    )

    # Только ошибки и критические события
    error_handler.setLevel(logging.ERROR)

    formatter = logging.Formatter(
        fmt=settings.logging.error_format, datefmt=settings.logging.date_format, style="{"
    )

    error_handler.setFormatter(formatter)

    return error_handler


def configure_third_party_loggers():
    """
    Настройка уровней логирования для сторонних библиотек
    """
    # SQLAlchemy
    logging.getLogger("sqlalchemy.engine").setLevel(
        getattr(logging, settings.logging.sqlalchemy_level)
    )
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)

    # Aiogram
    logging.getLogger("aiogram").setLevel(getattr(logging, settings.logging.aiogram_level))

    # HTTP библиотеки
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Uvicorn
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Отключаем слишком болтливые логи
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def setup_logging() -> None:
    """
    Основная функция настройки системы логирования
    """
    # Получаем корневой логгер
    root_logger = logging.getLogger()

    # Очищаем существующие обработчики
    root_logger.handlers.clear()

    # Устанавливаем общий уровень
    root_logger.setLevel(logging.DEBUG)

    # Добавляем обработчики
    handlers = []

    # Консольный вывод
    console_handler = setup_console_handler()
    handlers.append(console_handler)

    # Файловый вывод
    file_handler = setup_file_handler()
    if file_handler:
        handlers.append(file_handler)

    # Telegram логи
    telegram_handler = setup_telegram_handler()
    if telegram_handler:
        handlers.append(telegram_handler)

    # Логи ошибок
    error_handler = setup_error_handler()
    if error_handler:
        handlers.append(error_handler)

    # Добавляем все обработчики к корневому логгеру
    for handler in handlers:
        root_logger.addHandler(handler)

    # Настройка сторонних библиотек
    configure_third_party_loggers()

    # Логируем успешную настройку
    logger = logging.getLogger(__name__)
    logger.info(f"📝 Логирование настроено. Уровень: {settings.logging.level}")

    if settings.logging.file_path:
        logger.info(f"📁 Логи сохраняются в: {settings.logging.file_path}")

    if settings.debug:
        logger.debug("🐛 Режим отладки включен")


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер с заданным именем

    Args:
        name: Имя логгера (обычно __name__)
    """
    return logging.getLogger(name)


# Контекстный менеджер для временного изменения уровня логирования
class LogLevel:
    """
    Контекстный менеджер для временного изменения уровня логирования

    Пример:
    with LogLevel(logging.DEBUG):
        logger.debug("Этот лог будет показан")
    """

    def __init__(self, level: int, logger_name: str | None = None):
        self.level = level
        self.logger_name = logger_name
        self.original_level = None
        self.logger = None

    def __enter__(self):
        if self.logger_name:
            self.logger = logging.getLogger(self.logger_name)
        else:
            self.logger = logging.getLogger()

        self.original_level = self.logger.level
        self.logger.setLevel(self.level)

        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)


# Декоратор для логирования вызовов функций
def log_function_calls(logger_name: str | None = None):
    """
    Декоратор для автоматического логирования вызовов функций

    Args:
        logger_name: Имя логгера (по умолчанию используется имя модуля функции)
    """

    def decorator(func):
        import functools
        import time

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name or func.__module__)

            start_time = time.time()
            logger.debug(f"🔄 Вызов {func.__name__}(args={args}, kwargs={kwargs})")

            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(f"✅ {func.__name__} выполнена за {execution_time:.3f}с")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ Ошибка в {func.__name__} за {execution_time:.3f}с: {e}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name or func.__module__)

            start_time = time.time()
            logger.debug(f"🔄 Вызов {func.__name__}(args={args}, kwargs={kwargs})")

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(f"✅ {func.__name__} выполнена за {execution_time:.3f}с")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ Ошибка в {func.__name__} за {execution_time:.3f}с: {e}")
                raise

        # Возвращаем подходящий wrapper в зависимости от типа функции
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Экспорт основных компонентов
__all__ = [
    "ColoredFormatter",
    "LogLevel",
    "TelegramFormatter",
    "get_logger",
    "log_function_calls",
    "setup_logging",
]
