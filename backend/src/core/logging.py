import asyncio
import functools
import logging
import logging.handlers
import time
from collections.abc import Callable
from copy import copy
from pathlib import Path
from typing import Any, ClassVar, TypeVar

from rich.console import Console
from rich.logging import RichHandler

from .config import settings

console = Console()

F = TypeVar("F", bound=Callable[..., Any])


# --- Форматтеры ---


class TelegramFormatter(logging.Formatter):
    """
    Специальный форматтер для логов Telegram бота.
    Добавляет emoji в запись лога в зависимости от уровня.
    """

    EMOJI: ClassVar[dict[str, str]] = {
        "DEBUG": "🐛",
        "INFO": "📋",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨",
    }

    def format(self, record: logging.LogRecord) -> str:
        record_copy = copy(record)
        record_copy.emoji = self.EMOJI.get(record_copy.levelname, "📋")
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
    """
    Настройка обработчика для вывода в консоль через Rich.
    """
    # Создаем настроенную консоль для логов
    # Если заставляем терминал, то и цвета заставляем
    color_system = "truecolor" if settings.logging.rich_force_terminal else "auto"

    rich_console = Console(
        force_terminal=settings.logging.rich_force_terminal,
        color_system=color_system,
        width=settings.logging.rich_width,
    )

    console_handler = RichHandler(
        rich_tracebacks=True,  # Красивые цветные трейсбеки
        tracebacks_show_locals=settings.logging.rich_show_locals,  # Показывать значения переменных при ошибке
        tracebacks_suppress=settings.logging.rich_suppress,  # Скрывать шум библиотек
        show_time=True,
        show_level=True,
        show_path=False,
        markup=True,  # Разрешаем [bold red]...[/] в сообщениях
        console=rich_console,  # Используем настроенную консоль
    )

    # RichHandler сам добавляет время и уровень, поэтому формат message простой
    formatter = logging.Formatter(fmt="%(message)s", datefmt="[%X]")
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
    """Настройка уровней логирования для сторонних библиотек, чтобы убрать шум."""
    loggers_config = {
        "sqlalchemy.engine": settings.logging.sqlalchemy_level,
        "sqlalchemy.pool": "WARNING",
        "sqlalchemy.dialects": "WARNING",
        "aiogram": settings.logging.aiogram_level,
        "aiogram.event": "INFO",  # Чтобы видеть входящие апдейты, если уровень INFO
        "httpx": "WARNING",
        "httpcore": "WARNING",
        "uvicorn": "INFO",
        "uvicorn.access": "WARNING",  # WARNING скроет логи "GET / HTTP/1.1 200 OK"
        "uvicorn.error": "INFO",
        "multipart": "WARNING",
        "asyncio": "WARNING",
        "watchfiles": "WARNING",  # Убирает шум при авто-перезагрузке
    }
    for name, level in loggers_config.items():
        logging.getLogger(name).setLevel(getattr(logging, level.upper()))


def setup_logging() -> None:
    """Основная функция настройки системы логирования."""

    # 1. Применяем настройки Rich (если есть в конфиге)
    settings.logging.configure_rich()

    root_logger = logging.getLogger()

    # 2. Очищаем существующие хендлеры (важно для перезагрузки uvicorn)
    if root_logger.handlers:
        root_logger.handlers.clear()

    # 3. Устанавливаем базовый уровень
    root_logger.setLevel(settings.logging.level)

    # 4. Собираем обработчики
    handlers = [
        setup_console_handler(),
        setup_file_handler(),
        setup_telegram_handler(),
        setup_error_handler(),
    ]

    # 5. Добавляем только активные обработчики
    for handler in filter(None, handlers):
        root_logger.addHandler(handler)

    # 6. Настраиваем чужие библиотеки
    configure_third_party_loggers()


def get_logger(name: str) -> logging.Logger:
    """Получить логгер с заданным именем"""
    return logging.getLogger(name)


# --- Декораторы и Контекстные менеджеры ---


class LogLevel:
    """Контекстный менеджер для временного изменения уровня логирования"""

    def __init__(self, level: int, logger_name: str | None = None):
        self.level = level
        self.logger_name = logger_name
        self.original_level = None
        self.logger = None

    def __enter__(self):
        self.logger = (
            logging.getLogger(self.logger_name) if self.logger_name else logging.getLogger()
        )
        self.original_level = self.logger.level
        self.logger.setLevel(self.level)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.logger:
            self.logger.setLevel(self.original_level)


def log_function_calls(logger_name: str | None = None) -> Callable[[F], F]:
    """Декоратор для автоматического логирования вызовов функций"""

    def decorator(func: F) -> F:
        # Определяем логгер один раз
        logger = logging.getLogger(logger_name or func.__module__)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            logger.debug("🔄 Вызов %s", func.__name__)
            try:
                result = await func(*args, **kwargs)
                _log_success(logger, func.__name__, start_time)
                return result
            except Exception as e:
                _log_error(logger, func.__name__, start_time, e)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            logger.debug("🔄 Вызов %s", func.__name__)
            try:
                result = func(*args, **kwargs)
                _log_success(logger, func.__name__, start_time)
                return result
            except Exception as e:
                _log_error(logger, func.__name__, start_time, e)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def _log_success(logger: logging.Logger, func_name: str, start_time: float):
    execution_time = time.time() - start_time
    # Если функция выполняется дольше 1 секунды, меняем уровень лога и цвет сообщения
    if execution_time > 1.0:
        logger.warning("🐢 SLOW %s: %.3fс", func_name, execution_time)
    else:
        logger.debug("✅ %s: %.3fс", func_name, execution_time)


def _log_error(logger: logging.Logger, func_name: str, start_time: float, error: Exception):
    execution_time = time.time() - start_time
    logger.error(
        "❌ Ошибка в %s (%.3fс): %s",
        func_name,
        execution_time,
        error,
        exc_info=True,
    )
