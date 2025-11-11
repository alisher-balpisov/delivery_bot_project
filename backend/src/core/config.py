import string
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    """Конфигурация подключения к базе данных (SQLAlchemy)."""

    # URL для подключения к базе данных, например:
    # "postgresql+asyncpg://user:password@host:port/dbname"
    # Использование SecretStr предотвращает случайную утечку пароля в логах.
    url: SecretStr

    # --- Общие настройки движка SQLAlchemy ---
    # Логировать все SQL-запросы, выполняемые движком. Полезно для отладки.
    echo: bool = False
    # Использовать новое API SQLAlchemy 2.0.
    future: bool = True

    # --- Настройки пула соединений ---
    # Количество соединений, которые постоянно поддерживаются в пуле.
    pool_size: int = 10
    # Максимальное количество дополнительных соединений сверх pool_size при пиковой нагрузке.
    max_overflow: int = 5
    # Проверять "живучесть" соединения перед его использованием.
    # Помогает избежать ошибок "MySQL server has gone away" или аналогичных.
    pool_pre_ping: bool = True
    # Время в секундах, по истечении которого соединение будет пересоздано.
    # Предотвращает проблемы с устаревшими или закрытыми сетью соединениями.
    pool_recycle: int = 300  # 5 минут
    # Время в секундах, которое приложение будет ждать свободного соединения из пула.
    pool_timeout: int = 30

    # --- Настройки сессии SQLAlchemy ---
    # Не использовать, если работаете с `asyncio`. Управляется вручную.
    auto_flush: bool = False
    # Объекты не становятся недействительными (expired) после коммита сессии.
    # Позволяет продолжать использовать объекты после того, как транзакция завершена.
    expire_on_commit: bool = False

    def engine_kwargs(self) -> dict[str, Any]:
        """
        Собирает словарь аргументов для функции `create_async_engine()`.

        Returns:
            Словарь с параметрами для настройки движка SQLAlchemy.
        """
        return {
            "echo": self.echo,
            "future": self.future,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_recycle": self.pool_recycle,
            "pool_timeout": self.pool_timeout,
        }

    def session_kwargs(self) -> dict[str, Any]:
        """
        Собирает словарь аргументов для `sessionmaker()` или `async_sessionmaker()`.

        Returns:
            Словарь с параметрами для настройки сессии SQLAlchemy.
        """
        return {
            "autoflush": self.auto_flush,
            "expire_on_commit": self.expire_on_commit,
        }


class AuthConfig(BaseModel):
    """Конфигурация авторизации."""

    # Максимальное количество попыток ввода кода при регистрации.
    registration_max_attempts: int = 3
    registration_code_lifetime_hours: int = 5
    code_length: int = 8
    code_characters: str = string.ascii_uppercase + string.digits
    max_retries: int = 10


class MiddlewareConfig(BaseModel):
    """Конфигурация Middleware, в частности CORS (Cross-Origin Resource Sharing)."""

    # Список разрешенных источников (origins). Устанавливается в `Settings`.
    allow_origins: list[str] = []
    # Разрешить передачу cookie и заголовков авторизации.
    allow_credentials: bool = True
    # Разрешенные HTTP-методы.
    allow_methods: list[str] = ["*"]
    # Разрешенные HTTP-заголовки.
    allow_headers: list[str] = ["*"]

    def cors_kwargs(self) -> dict[str, Any]:
        """
        Собирает словарь аргументов для `CORSMiddleware`.

        Returns:
            Словарь с параметрами для настройки CORS.
        """
        return {
            "allow_origins": self.allow_origins,
            "allow_credentials": self.allow_credentials,
            "allow_methods": self.allow_methods,
            "allow_headers": self.allow_headers,
        }


class TelegramConfig(BaseModel):
    """Конфигурация Telegram-бота."""

    bot_token: SecretStr  # Токен, полученный от @BotFather.
    # Полный URL для получения обновлений через вебхук (например, https://example.com/webhook).
    webhook_url: str | None = None
    # Секретный токен для проверки подлинности запросов от Telegram.
    webhook_secret: str | None = None
    # Путь для вебхука.
    webhook_path: str = "/webhook"
    # Использовать вебхуки (True) или long polling (False).
    use_webhook: bool = False
    # Пропускать накопившиеся обновления при перезапуске бота.
    skip_updates: bool = True
    # Режим разметки сообщений по умолчанию (HTML, MarkdownV2).
    parse_mode: str = "HTML"
    # Отключить автоматический предпросмотр ссылок в сообщениях.
    disable_web_page_preview: bool = True
    # Количество сообщений для ограничения (т.н. "т/роттлинг").
    rate_limit_messages: int = 30
    # Временное окно для ограничения в секундах.
    rate_limit_window: int = 60


class FileStorageConfig(BaseModel):
    """Конфигурация для работы с файлами."""

    # Директория для загрузки файлов.
    upload_dir: Path = Path("uploads")
    # Максимальный размер файла в байтах.
    max_file_size: int = 20 * 1024 * 1024
    # Список разрешенных расширений для загружаемых изображений.
    allowed_photo_formats: list[str] = ["jpg", "jpeg", "png", "webp", "heic"]
    max_photo_width: int = 1920  # Максимальная ширина изображения в пикселях.
    max_photo_height: int = 1080  # Максимальная высота изображения в пикселях.
    # Качество сжатия изображений.
    photo_quality: int = 85


class LoggingConfig(BaseModel):
    """Конфигурация системы логирования."""

    level: str = "DEBUG"  # Уровень логирования (DEBUG, INFO, WARNING, ERROR).
    # Формат для консольных логов.
    format: str = "{asctime} | {levelname} | {name} | {message}"
    # Расширенный формат для файловых логов с указанием файла и функции.
    file_format: str = "{asctime} | {levelname} | {name}:{lineno} | {funcName} | {message}"
    # Формат для логов, отправляемых в Telegram.
    telegram_format: str = "{asctime} | {emoji} {levelname} | {name} | {message}"
    # Детальный формат для логов ошибок с трассировкой.
    error_format: str = (
        "{asctime} | 🚨 {levelname} | {name}:{lineno} | {funcName}\n"
        "Message: {message}\nPath: {pathname}\n{exc_info}\n" + "-" * 80
    )
    date_format: str = "%Y-%m-%d %H:%M:%S"  # Формат даты в логах.
    file_path: Path | None = None  # Путь к файлу логов. Если None, логи в файл не пишутся.
    # Максимальный размер файла логов перед ротацией.
    max_file_size: int = 20 * 1024 * 1024
    # Количество хранимых архивных файлов логов.
    backup_count: int = 5
    # Уровень логирования для библиотеки SQLAlchemy.
    sqlalchemy_level: str = "WARNING"
    # Уровень логирования для библиотеки aiogram.
    aiogram_level: str = "INFO"

    def handler_kwargs(self) -> dict[str, Any]:
        """
        Собирает словарь аргументов для `RotatingFileHandler`.

        Returns:
            Словарь с параметрами для настройки файлового обработчика логов.
        """
        return {
            "maxBytes": self.max_file_size,
            "backupCount": self.backup_count,
            "encoding": "utf-8",
        }


class BusinessConfig(BaseModel):
    """Настройки, определяющие бизнес-логику и правила приложения."""

    # Максимальное количество активных заказов на одного курьера.
    max_orders_per_courier: int | None = None
    # Время бездействия курьера в секундах, после которого он считается оффлайн.
    courier_inactive_timeout: int | None = None
    # Время в секундах для автоматической отмены нового заказа, если его никто не взял.
    order_auto_cancel_timeout: int | None = None
    # Максимальное время на выполнение заказа в секундах.
    order_completion_timeout: int | None = None
    min_order_price: float | None = None  # Минимальная стоимость заказа.
    max_order_price: float | None = None  # Максимальная стоимость заказа.
    default_delivery_price: float | None = None  # Базовая стоимость доставки.
    # Множитель стоимости доставки в ночное время.
    night_delivery_multiplier: float | None = None
    work_start_hour: int | None = None  # Начало рабочего дня.
    work_end_hour: int | None = None  # Конец рабочего дня.
    # Количество повторных попыток отправки уведомлений в случае сбоя.
    notification_retry_attempts: int | None = None
    # Задержка между повторными попытками в секундах.
    notification_retry_delay: int | None = None


class AdminConfig(BaseModel):
    """Конфигурация для администрирования."""

    # Список Telegram ID пользователей, обладающих правами супер-администратора.
    super_admin_telegram_ids: list[int] = []
    # URL для доступа к внешней админ-панели (если есть).
    admin_panel_url: str | None = None
    # Интервал проверки состояния сервиса (health-check) в секундах.
    health_check_interval: int = 300  # 5 минут
    # Включить/выключить сбор метрик (например, для Prometheus).
    metrics_enabled: bool = True

    @field_validator("super_admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> list[int]:
        """
        Позволяет задавать список ID админов строкой через запятую
        (удобно для переменных окружения).
        Например: "12345, 67890" -> [12345, 67890].
        """
        if isinstance(v, str):
            return [int(id_str.strip()) for id_str in v.split(",") if id_str.strip().isdigit()]
        return v


class JwtConfig(BaseModel):
    """Конфигурация для работы с JWT (JSON Web Tokens)."""

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    refresh_secret_key: SecretStr | None = None  # Если None, используем secret_key

    @property
    def refresh_secret(self) -> str:
        """Возвращает секрет для refresh токена"""
        return (
            self.refresh_secret_key.get_secret_value()
            if self.refresh_secret_key
            else self.secret_key.get_secret_value()
        )


class RedisConfig(BaseModel):
    """Конфигурация для подключения к Redis."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    state_ttl: int | None = None
    data_ttl: int | None = None


class Settings(BaseSettings):
    """
    Основной класс настроек приложения.

    Собирает все конфигурационные модели в единую структуру и загружает
    значения из переменных окружения и .env файла.
    """

    # --- Мета-информация о приложении ---
    app_name: str = "Delivery Bot"
    app_version: str = "0.1.0"
    # Режим отладки. Влияет на уровень логирования, отображение ошибок и т.д.
    # В production должен быть False.
    debug: bool = True
    # Окружение: 'development', 'staging', 'production'.
    environment: str = "development"

    # --- Вложенные конфигурационные блоки ---
    redis: RedisConfig = Field(default_factory=RedisConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)  # type: ignore
    auth: AuthConfig = Field(default_factory=AuthConfig)  # type: ignore
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)  # type: ignore
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)  # type: ignore
    file_storage: FileStorageConfig = Field(default_factory=FileStorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    business: BusinessConfig = Field(default_factory=BusinessConfig)  # type: ignore
    admin: AdminConfig = Field(default_factory=AdminConfig)
    jwt: JwtConfig = Field(default_factory=JwtConfig)  # type: ignore

    # --- Настройки API (FastAPI) ---
    api_host: str = "localhost"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    @property
    def docs_url(self) -> str | None:
        """Возвращает URL для Swagger UI (docs) только в режиме отладки."""
        return "/docs" if self.debug else None

    @property
    def redoc_url(self) -> str | None:
        """Возвращает URL для ReDoc только в режиме отладки."""
        return "/redoc" if self.debug else None

    @property
    def is_production(self) -> bool:
        """Возвращает True, если окружение — 'production'."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Возвращает True, если окружение — 'development'."""
        return self.environment == "development"

    @model_validator(mode="after")
    def _validate_settings(self) -> "Settings":
        """
        Выполняет дополнительную валидацию и настройку после инициализации всех полей.
        """
        # Динамически настраиваем CORS в зависимости от режима debug.
        if self.debug:
            self.middleware.allow_origins = ["*"]
        else:
            # ВАЖНО: В production здесь должен быть явный список доменов,
            # например: ["https://my-app.com", "https://admin.my-app.com"]
            self.middleware.allow_origins = []

        # Проверяем консистентность настроек для production окружения.
        if self.is_production:
            if self.debug:
                raise ValueError("DEBUG не должен быть включен в 'production' окружении.")
            if self.telegram.use_webhook and not self.telegram.webhook_url:
                raise ValueError("WEBHOOK_URL обязателен при use_webhook=True в 'production'.")

        return self

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",  # Загружать переменные из файла .env.
        env_file_encoding="utf-8",  # Кодировка файла .env.
        # Разделитель для вложенных моделей в переменных окружения
        # (например, DATABASE__URL для settings.database.url).
        env_nested_delimiter="__",
        case_sensitive=False,  # Имена переменных окружения регистронезависимы.
        extra="ignore",  # Игнорировать лишние переменные окружения.
    )


settings = Settings()


# --- Функции-хелперы для удобного доступа к секретным значениям ---


def get_database_url() -> str:
    """Возвращает URL базы данных в виде обычной строки."""
    return settings.database.url.get_secret_value()


def get_bot_token() -> str:
    """Возвращает токен Telegram-бота в виде обычной строки."""
    return settings.telegram.bot_token.get_secret_value()


def get_jwt_secret() -> str:
    """Возвращает секретный ключ JWT в виде обычной строки."""
    return settings.jwt.secret_key.get_secret_value()


def is_admin(telegram_id: int) -> bool:
    """
    Проверяет, является ли пользователь супер-администратором.

    Args:
        telegram_id: ID пользователя в Telegram.

    Returns:
        True, если ID есть в списке супер-админов, иначе False.
    """
    return telegram_id in settings.admin.super_admin_telegram_ids


def get_upload_path() -> Path:
    """
    Возвращает путь к директории для загрузок (без её создания).

    Returns:
        Объект Path с путём к директории.
    """
    return Path(settings.file_storage.upload_dir)


def ensure_upload_dir_exists():
    """
    Создает директорию для загрузок, если она не существует.
    Эту функцию безопасно вызывать при старте приложения.
    """
    get_upload_path().mkdir(parents=True, exist_ok=True)


# Определяет публичный API модуля. При импорте `from config import *`
# будут импортированы только перечисленные здесь объекты.
__all__ = [
    "AdminConfig",
    "AuthConfig",
    "BusinessConfig",
    "DatabaseConfig",
    "FileStorageConfig",
    "JwtConfig",
    "LoggingConfig",
    "RedisConfig",
    "Settings",
    "TelegramConfig",
    "ensure_upload_dir_exists",
    "get_bot_token",
    "get_database_url",
    "get_jwt_secret",
    "get_upload_path",
    "is_admin",
    "settings",
]
