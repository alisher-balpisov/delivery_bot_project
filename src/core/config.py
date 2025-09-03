from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    """Конфигурация базы данных."""

    # URL подключения к БД
    URL: SecretStr

    # Общие настройки движка SQLAlchemy
    echo: bool = False  # Логировать SQL-запросы (удобно при отладке)
    future: bool = True  # Использовать новое API SQLAlchemy (>=1.4)

    # Настройки пула соединений
    pool_size: int = 10  # Постоянное количество соединений в пуле
    max_overflow: int = 5  # Доп. соединения сверх pool_size при пике
    pool_pre_ping: bool = True  # Проверять соединение перед использованием (устраняет ошибки "MySQL server has gone away")
    pool_recycle: int = 300  # Пересоздавать соединение через X секунд (устаревшие коннекты)
    pool_timeout: int = 30  # Таймаут ожидания свободного соединения

    # Настройки сессии SQLAlchemy
    auto_commit: bool = False  # Автоматический commit (обычно False)
    auto_flush: bool = False  # Автоматический flush перед запросами
    expire_on_commit: bool = False  # Не инвалидировать объекты после commit

    def engine_kwargs(self) -> dict:
        """Собирает kwargs для create_async_engine()."""
        return {
            "echo": self.echo,
            "future": self.future,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_recycle": self.pool_recycle,
            "pool_timeout": self.pool_timeout,
        }

    def session_kwargs(self) -> dict:
        """Собирает kwargs для sessionmaker()."""
        return {
            "autocommit": self.auto_commit,
            "autoflush": self.auto_flush,
            "expire_on_commit": self.expire_on_commit,
        }


class MiddlewareConfig(BaseModel):
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]

    @property
    def allow_origins(self) -> list[str]:
        """Список разрешённых CORS-источников."""
        return ["*"] if settings.debug else []

    def cors_kwargs(self) -> dict:
        """Собирает kwargs для add_middleware()."""
        return {
            "allow_origins": self.allow_origins,
            "allow_credentials": self.allow_credentials,
            "allow_methods": self.allow_methods,
            "allow_headers": self.allow_headers,
        }


class TelegramConfig(BaseModel):
    """Конфигурация Telegram-бота."""

    bot_token: SecretStr  # Токен бота
    webhook_url: str | None = None  # Полный URL вебхука (если используется)
    webhook_secret: str | None = None  # Секрет для подписи вебхука
    webhook_path: str = "/webhook"  # Путь вебхука
    use_webhook: bool = False  # True — использовать вебхуки, False — long polling
    parse_mode: str = "HTML"  # Режим форматирования сообщений
    disable_web_page_preview: bool = True  # Отключить предпросмотр ссылок
    rate_limit_messages: int = 30  # Кол-во сообщений в окне
    rate_limit_window: int = 60  # Окно ограничения в секундах


class SecurityConfig(BaseModel):
    """Конфигурация безопасности."""

    secret_key: SecretStr  # Ключ для подписи JWT и др.
    algorithm: str = "HS256"  # Алгоритм JWT
    access_token_expire_minutes: int = 30 * 24 * 60  # Время жизни токена (30 дней)
    bcrypt_rounds: int = 12  # Количество раундов хэширования пароля


class RedisConfig(BaseModel):
    """Конфигурация Redis."""

    url: str = "redis://localhost:6379/0"  # URL подключения к Redis
    max_connections: int = 20  # Максимальное количество соединений
    user_cache_ttl: int = 300  # TTL кэша пользователя
    order_cache_ttl: int = 60  # TTL кэша заказа


class FileStorageConfig(BaseModel):
    """Конфигурация файлового хранилища."""

    upload_dir: Path = Path("uploads")  # Каталог загрузки файлов
    max_file_size: int = 20 * 1024 * 1024  # Максимальный размер файла (20 МБ)
    allowed_photo_formats: list[str] = [
        "jpg",
        "jpeg",
        "png",
        "webp",
        "heic",
    ]  # Разрешённые форматы фото
    max_photo_width: int = 1920  # Максимальная ширина фото
    max_photo_height: int = 1080  # Максимальная высота фото
    photo_quality: int = 85  # Качество фото при сжатии


class LoggingConfig(BaseModel):
    """Конфигурация логирования."""

    level: str = "INFO"  # Уровень логирования
    format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"  # Формат строки лога
    file_format: str = (
        "%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(funcName)s | %(message)s"
    )
    telegram_format: str = "%(asctime)s | %(emoji)s %(levelname)s | %(name)s | %(message)s"
    error_format: str = (
        "%(asctime)s | 🚨 %(levelname)s | %(name)s:%(lineno)d | %(funcName)s\n"
        "Message: %(message)s\n"
        "Path: %(pathname)s\n"
        "%(exc_info)s\n"
        "-" * 80
    )
    date_format: str = "%Y-%m-%d %H:%M:%S"
    file_path: Path | None = None  # Путь к файлу логов
    max_file_size: int = 20 * 1024 * 1024  # Максимальный размер файла логов
    backup_count: int = 5  # Кол-во ротаций
    sqlalchemy_level: str = "WARNING"  # Уровень логов SQLAlchemy
    aiogram_level: str = "INFO"  # Уровень логов aiogram

    def handler_kwargs(self) -> dict:
        return {
            "maxBytes": self.max_file_size,
            "backupCount": self.backup_count,
            "encoding": settings.default_encoding,
        }


class BusinessConfig(BaseModel):
    """Бизнес-правила и ограничения."""

    max_orders_per_courier: int = 5  # Максимум заказов на курьера
    courier_inactive_timeout: int = 3600  # Время бездействия курьера (сек)
    order_auto_cancel_timeout: int = 1800  # Таймаут автоотмены заказа
    order_completion_timeout: int = 86400  # Таймаут выполнения заказа
    min_order_price: float = 50.0  # Минимальная цена заказа
    max_order_price: float = 10000.0  # Максимальная цена заказа
    default_delivery_price: float = 200.0  # Базовая цена доставки
    night_delivery_multiplier: float = 1.5  # Множитель ночной доставки
    work_start_hour: int = 8  # Начало рабочего времени
    work_end_hour: int = 22  # Конец рабочего времени
    notification_retry_attempts: int = 3  # Кол-во попыток повторной отправки уведомлений
    notification_retry_delay: int = 30  # Задержка между попытками (сек)


class AdminConfig(BaseModel):
    """Конфигурация администрирования."""

    super_admin_telegram_ids: list[int] = []  # Список ID супер-админов
    admin_panel_url: str | None = None  # URL админ-панели
    health_check_interval: int = 300  # Интервал health-check (сек)
    metrics_enabled: bool = True  # Включена ли метрика

    @field_validator("super_admin_telegram_ids", mode="before")
    def parse_admin_ids(cls, v):
        """
        Позволяет передавать список ID админов строкой через запятую
        (например, из переменных окружения).
        """
        if isinstance(v, str):
            return [int(id_str.strip()) for id_str in v.split(",") if id_str.strip().isdigit()]
        return v


class Settings(BaseSettings):
    """Основные настройки приложения."""

    app_name: str = "Delivery Bot"
    app_version: str = "0.1.0"
    debug: bool = True  # Режим отладки
    environment: str = "development"  # Окружение: development/production

    # Вложенные конфиги
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    file_storage: FileStorageConfig = Field(default_factory=FileStorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    business: BusinessConfig = Field(default_factory=BusinessConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)

    api_host: str = "localhost"
    api_port: int = 5432
    api_prefix: str = "/api/v1"

    default_encoding: str = "utf-8"

    @property
    def docs_url(self) -> str | None:
        """Возвращает URL для Swagger UI (docs) только в debug."""
        return "/docs" if self.debug else None

    @property
    def redoc_url(self) -> str | None:
        """Возвращает URL для ReDoc только в debug."""
        return "/redoc" if self.debug else None

    @property
    def is_production(self) -> bool:
        """True, если окружение — production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """True, если окружение — development."""
        return self.environment == "development"

    @model_validator(mode="after")
    def check_production_settings(self) -> "Settings":
        """
        Дополнительная валидация для production.

        Проверяет, что debug выключен и webhook_url указан, если use_webhook=True.
        """
        if self.environment == "production":
            if self.debug:
                raise ValueError(
                    "DEBUG не должен быть включен в продакшене (environment='production')"
                )
            if self.telegram.use_webhook and not self.telegram.webhook_url:
                raise ValueError("WEBHOOK_URL обязателен при use_webhook=True в продакшене")
        return self

    # Конфиг для pydantic_settings
    model_config = SettingsConfigDict(
        env_file=".env",  # Загружать переменные из .env
        env_file_encoding=default_encoding,
        env_nested_delimiter="__",  # Для вложенных конфигов DATABASE__URL
        case_sensitive=False,
    )


# Создаём глобальный объект настроек
settings = Settings()


# Функции для получения специфических настроек
def get_database_url() -> str:
    return settings.database.URL


def get_bot_token() -> str:
    return settings.telegram.bot_token


def get_redis_url() -> str:
    return settings.redis.url


def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin.super_admin_telegram_ids


def get_upload_dir() -> Path:
    """Получить директорию для загрузок. Создаёт, если нет."""
    upload_dir = settings.file_storage.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


# Экспорт основных классов/функций для удобства импорта
__all__ = [
    "AdminConfig",
    "BusinessConfig",
    "DatabaseConfig",
    "FileStorageConfig",
    "LoggingConfig",
    "RedisConfig",
    "SecurityConfig",
    "Settings",
    "TelegramConfig",
    "get_bot_token",
    "get_database_url",
    "get_redis_url",
    "get_upload_dir",
    "is_admin",
    "settings",
]
