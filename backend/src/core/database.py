from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.src.core.config import settings
from backend.src.core.logging import get_logger

logger = get_logger(__name__)

# Создаём асинхронный движок SQLAlchemy
engine = create_async_engine(
    settings.database.url.get_secret_value(), **settings.database.engine_kwargs()
)

# Фабрика для создания асинхронных сессий
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, **settings.database.session_kwargs()
)


class Base(DeclarativeBase):
    """
    Базовый класс для всех ORM-моделей.

    Содержит улучшенный __repr__, который
    выводит id и указанные в __repr_attrs__ поля.
    """

    # Атрибуты, которые нужно показывать в __repr__
    __repr_attrs__: tuple[str, ...] = ()
    # Максимальная длина значения атрибута в __repr__
    __repr_max_length__: int = 15

    @property
    def _id_str(self) -> str | None:
        """
        Возвращает строковое представление id,
        если атрибут 'id' присутствует и не None.
        """
        return str(self.id) if getattr(self, "id", None) is not None else None

    @property
    def _repr_attrs_str(self) -> str:
        """
        Формирует строку с атрибутами для __repr__.

        Обрезает слишком длинные значения до __repr_max_length__.
        Для строк добавляет кавычки.
        """
        if not self.__repr_attrs__:
            return ""

        max_length = self.__repr_max_length__
        values: list[str] = []
        single_attr = len(self.__repr_attrs__) == 1

        for key in self.__repr_attrs__:
            # Проверяем, что атрибут реально существует
            if not hasattr(self, key):
                raise KeyError(
                    f"Неверный атрибут '{key}' в __repr_attrs__ класса {self.__class__.__name__}"
                )

            val = getattr(self, key)
            is_str = isinstance(val, str)

            val_str = str(val)
            if len(val_str) > max_length:
                val_str = val_str[:max_length] + "..."

            if is_str:
                val_str = f"'{val_str}'"

            values.append(val_str if single_attr else f"{key}:{val_str}")

        return " ".join(values)

    def __repr__(self) -> str:
        """
        Красивое строковое представление модели.

        Пример: <User #1 name:'John'>
        """
        id_part = f"#{self._id_str}" if self._id_str else ""
        attrs_part = f" {self._repr_attrs_str}" if self._repr_attrs_str else ""
        return f"<{self.__class__.__name__} {id_part}{attrs_part}>"


async def get_db():
    """
    Асинхронный генератор зависимости для FastAPI.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """
    Создаёт все таблицы, описанные в метаданных Base.
    """
    logger.info("🔨 Создание таблиц в базе данных...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ Таблицы созданы успешно")


async def drop_tables() -> None:
    """
    Удаляет все таблицы из базы данных.
    ОСТОРОЖНО: используйте только для разработки!
    """
    if settings.is_production:
        raise RuntimeError("❌ Нельзя удалять таблицы в продакшене!")

    logger.warning("⚠️ Удаление всех таблиц из базы данных...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.info("✅ Таблицы удалены")


async def check_database_connection() -> bool:
    """
    Проверяет соединение с базой данных.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка соединения с БД: {e}")
        return False


def _import_models() -> None:
    """
    Импортирует все модели для регистрации в метаданных Base.
    Вызывается один раз для избежания дублирования кода.
    """
    from backend.src.models.shop import Shop  # noqa
    from backend.src.models.courier import Courier  # noqa
    from backend.src.models.user import User  # noqa
    from backend.src.models.order import Order  # noqa
    from backend.src.models.dispute import Dispute  # noqa
    from backend.src.models.photo_report import PhotoReport  # noqa
    from backend.src.models.registration_code import RegistrationCode  # noqa
    from backend.src.models.zone import Zone  # noqa


async def init_db() -> None:
    """
    Инициализация базы данных при запуске приложения.
    """
    logger.info("🔧 Инициализация базы данных...")

    try:
        # Проверка соединения
        if not await check_database_connection():
            raise ConnectionError("Не удается подключиться к базе данных")

        # Импорт всех моделей для регистрации в метаданных
        _import_models()

        logger.info("✅ Соединение с базой данных установлено")

        # Лог количества зарегистрированных таблиц для диагностики
        tables = list(Base.metadata.tables.keys())
        logger.info(f"📊 Зарегистрировано {len(tables)} таблиц: {', '.join(tables)}")

        # Создание таблиц (если не существуют)
        await create_tables()

        logger.info("✅ База данных инициализирована успешно")

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        raise


async def close_db() -> None:
    """
    Закрытие соединений с базой данных при завершении приложения.
    """
    logger.info("🔒 Закрытие соединений с базой данных...")

    try:
        # Закрытие пула соединений
        await engine.dispose()
        logger.info("✅ Соединения с базой данных закрыты")

    except Exception as e:
        logger.error(f"❌ Ошибка при закрытии соединений с БД: {e}")
        raise


async def reset_database() -> None:
    """
    Полный сброс базы данных (удаление + создание таблиц).
    ОСТОРОЖНО: используйте только для разработки!
    """
    if settings.is_production:
        raise RuntimeError("❌ Нельзя сбрасывать базу данных в продакшене!")

    logger.warning("🔄 Полный сброс базы данных...")

    # Импорт всех моделей для регистрации в метаданных
    _import_models()

    await drop_tables()
    await create_tables()

    logger.info("✅ База данных сброшена и пересоздана")


async def get_db_session() -> AsyncSession:
    """
    Получить новую сессию базы данных для использования вне FastAPI.
    Не забудьте закрыть сессию после использования!

    Пример использования:
    async with get_db_session() as session:
        # работа с БД
        pass
    """
    return AsyncSessionLocal()


# Экспорт основных компонентов
__all__ = [
    "AsyncSessionLocal",
    "Base",
    "_import_models",
    "check_database_connection",
    "close_db",
    "create_tables",
    "drop_tables",
    "engine",
    "get_db",
    "get_db_session",
    "init_db",
    "reset_database",
]
