import asyncio
import logging
import logging.handlers
import sys
from copy import copy
from pathlib import Path
from typing import ClassVar

from .config import settings


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для консоли.
    """

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Создает копию record, чтобы безопасно добавить цвет,
        и затем форматирует сообщение.
        """
        # Создаем поверхностную копию, чтобы не изменять оригинал
        record_copy = copy(record)
        level_name = record_copy.levelname
        if level_name in self.COLORS:
            record_copy.levelname = f"{self.COLORS[level_name]}{level_name}{self.RESET}"
        # Форматируем сообщение, используя измененную копию
        return super().format(record_copy)


class TelegramFormatter(logging.Formatter):
    """
    Специальный форматтер для логов Telegram бота.
    Добавляет emoji в запись лога.
    """

    def format(self, record: logging.LogRecord) -> str:
        emoji_map = {"DEBUG": "🐛", "INFO": "📋", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}
        # Используем copy, чтобы следовать лучшим практикам, как и в ColoredFormatter
        record_copy = copy(record)
        record_copy.emoji = emoji_map.get(record_copy.levelname, "📋")
        return super().format(record_copy)


# --- Вспомогательные функции для создания обработчиков ---


def _create_rotating_file_handler(
    filename: Path, level: int, formatter: logging.Formatter, handler_kwargs: dict
) -> logging.handlers.RotatingFileHandler:
    """Вспомогательная функция для создания файлового обработчика с ротацией."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(filename=str(filename), **handler_kwargs)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler


def setup_console_handler() -> logging.Handler:
    """Настройка обработчика для вывода в консоль."""
    console_handler = logging.StreamHandler(sys.stdout)
    formatter_class = (
        ColoredFormatter if settings.debug and sys.stdout.isatty() else logging.Formatter
    )

    formatter = formatter_class(
        fmt=settings.logging.format, datefmt=settings.logging.date_format, style="{"
    )
    console_handler.setFormatter(formatter)
    console_handler.setLevel(settings.logging.level)
    return console_handler


def setup_file_handler() -> logging.Handler | None:
    """Настройка обработчика для записи в основной файл логов."""
    if not settings.logging.file_path:
        return None

    log_file = Path(settings.logging.file_path)
    formatter = logging.Formatter(
        fmt=settings.logging.file_format, datefmt=settings.logging.date_format, style="{"
    )

    return _create_rotating_file_handler(
        filename=log_file,
        level=settings.logging.level,
        formatter=formatter,
        handler_kwargs=settings.logging.handler_kwargs(),
    )


def setup_telegram_handler() -> logging.Handler | None:
    """Настройка специального обработчика для логов Telegram бота."""
    if not settings.logging.file_path:
        return None

    bot_log_file = Path(settings.logging.file_path).parent / "telegram_bot.log"
    formatter = TelegramFormatter(
        fmt=settings.logging.telegram_format, datefmt=settings.logging.date_format, style="{"
    )

    return _create_rotating_file_handler(
        filename=bot_log_file,
        level=settings.logging.level,
        formatter=formatter,
        handler_kwargs=settings.logging.handler_kwargs(),
    )


def setup_error_handler() -> logging.Handler | None:
    """Отдельный обработчик только для ошибок (ERROR и CRITICAL)."""
    if not settings.logging.file_path:
        return None

    error_log_file = Path(settings.logging.file_path).parent / "errors.log"
    formatter = logging.Formatter(
        fmt=settings.logging.error_format, datefmt=settings.logging.date_format, style="{"
    )

    return _create_rotating_file_handler(
        filename=error_log_file,
        level=logging.ERROR,
        formatter=formatter,
        handler_kwargs=settings.logging.handler_kwargs(),
    )


# --- Основные функции настройки ---


def configure_third_party_loggers() -> None:
    """Настройка уровней логирования для сторонних библиотек."""
    # Код остался без изменений, он и так был хорош
    loggers_config = {
        "sqlalchemy.engine": settings.logging.sqlalchemy_level,
        "sqlalchemy.pool": "WARNING",
        "sqlalchemy.dialects": "WARNING",
        "aiogram": settings.logging.aiogram_level,
        "httpx": "WARNING",
        "httpcore": "WARNING",
        "uvicorn.access": "INFO",
        "uvicorn.error": "INFO",
        "multipart": "WARNING",
        "asyncio": "WARNING",
    }
    for name, level in loggers_config.items():
        logging.getLogger(name).setLevel(getattr(logging, level.upper()))


def setup_logging() -> None:
    """Основная функция настройки системы логирования."""
    root_logger = logging.getLogger()

    # Проверка, чтобы избежать повторной инициализации.
    # clear() остается для случаев, когда нужна принудительная перезагрузка.
    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.setLevel(logging.DEBUG)

    # Собираем обработчики, отфильтровывая None
    handlers = [
        setup_console_handler(),
        setup_file_handler(),
        setup_telegram_handler(),
        setup_error_handler(),
    ]

    for handler in filter(None, handlers):
        root_logger.addHandler(handler)

    configure_third_party_loggers()

    logger = logging.getLogger(__name__)
    logger.info("📝 Логирование настроено. Уровень: %s", settings.logging.level)
    if settings.logging.file_path:
        logger.info("📁 Логи сохраняются в: %s", settings.logging.file_path)
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
