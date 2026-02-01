"""
Точка входа для запуска Telegram-бота с автоматической перезагрузкой.

Использует watchfiles для мониторинга изменений в файлах проекта
и автоматически перезапускает бота при обнаружении изменений.

Запуск:
    python run_bot.py
"""

import logging
import sys
from pathlib import Path

from watchfiles import DefaultFilter, run_process

# --- Настройка базового логирования ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


class BotFileFilter(DefaultFilter):
    """Фильтр для мониторинга только релевантных файлов."""

    def __call__(self, change, path: str) -> bool:
        if any(x in path for x in ["__pycache__", ".pyc", ".log", ".git"]):
            return False
        return super().__call__(change, path)


def start():
    """
    Импортирует и запускает основную функцию бота.

    Импорт выполняется внутри функции, чтобы обеспечить
    возможность перезагрузки модулей при изменениях.
    """
    try:
        from bot.main import main

        logger.info("Запуск Telegram-бота...")
        main()
    except ImportError as e:
        logger.error(f"Ошибка импорта модуля бота: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Определяем корневую директорию проекта
    project_root = Path(__file__).parent

    # Директории для мониторинга
    watch_paths = [
        project_root / "bot",
        project_root / "backend" / "src",
    ]

    # Фильтруем только существующие директории
    existing_paths = [str(path) for path in watch_paths if path.exists()]

    if not existing_paths:
        logger.warning(
            "⚠️  Не найдены директории для мониторинга. "
            "Бот будет запущен без автоматической перезагрузки."
        )
        start()
    else:
        logger.info(f"Мониторинг изменений в: {', '.join(existing_paths)}")

        try:
            run_process(
                *existing_paths,
                target=start,
                watch_filter=BotFileFilter(),
            )
        except KeyboardInterrupt:
            logger.info("\nПолучен сигнал остановки. Завершение работы...")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
            sys.exit(1)
