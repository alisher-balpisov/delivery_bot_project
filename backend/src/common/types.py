"""
Общие типы и протоколы для проекта.

Этот модуль содержит переиспользуемые типы, Protocol классы
и type aliases для улучшения типизации.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from backend.src.common.enums import OrderStatus, UserRole
from sqlalchemy.ext.asyncio import AsyncSession

# ==============================================================================
# Generic типы
# ==============================================================================

T = TypeVar("T")
ModelT = TypeVar("ModelT")


# ==============================================================================
# Протоколы для моделей
# ==============================================================================


class HasId(Protocol):
    """Протокол для моделей с полем id."""

    id: int


class HasUserId(Protocol):
    """Протокол для моделей с полем user_id."""

    user_id: int


class HasStatus(Protocol):
    """Протокол для моделей с полем status."""

    status: OrderStatus | str


# ==============================================================================
# Callback типы
# ==============================================================================

# Функция обратного вызова, не возвращающая значение
VoidCallback = Callable[[], None]
AsyncVoidCallback = Callable[[], Awaitable[None]]

# Функция обратного вызова с одним параметром
CallbackWithParam = Callable[[T], None]
AsyncCallbackWithParam = Callable[[T], Awaitable[None]]

# Функция обратного вызова, возвращающая значение
ValueCallback = Callable[[], T]
AsyncValueCallback = Callable[[], Awaitable[T]]


# ==============================================================================
# Database типы
# ==============================================================================

# Тип для сессии базы данных
DbSession = AsyncSession

# Функция получения сессии БД
DbSessionFactory = Callable[[], Awaitable[AsyncSession]]


# ==============================================================================
# API типы
# ==============================================================================

# Словарь с данными запроса/ответа
JsonDict = dict[str, Any]

# Словарь с query параметрами
QueryParams = dict[str, str | int | bool | None]

# Словарь с headers
Headers = dict[str, str]


# ==============================================================================
# Протокол для сервисов
# ==============================================================================


class BaseService(Protocol):
    """Базовый протокол для сервисов."""

    db: AsyncSession


class CRUDService(BaseService, Protocol):
    """Протокол для CRUD сервисов."""

    async def get(self, id: int) -> ModelT: ...
    async def create(self, data: JsonDict) -> ModelT: ...
    async def update(self, id: int, data: JsonDict) -> ModelT: ...
    async def delete(self, id: int) -> None: ...


# ==============================================================================
# Фильтры
# ==============================================================================

# Словарь с параметрами фильтрации
FilterParams = dict[str, Any]

# Функция для применения фильтров
FilterFunction = Callable[[Any, FilterParams], Any]


# ==============================================================================
# Права доступа
# ==============================================================================

# Набор разрешённых ролей
AllowedRoles = set[UserRole]

# Функция проверки прав доступа
PermissionCheck = Callable[[Any, Any], Awaitable[bool]]


# ==============================================================================
# Экспорт
# ==============================================================================

__all__ = [
    "AllowedRoles",
    "AsyncCallbackWithParam",
    "AsyncValueCallback",
    "AsyncVoidCallback",
    "BaseService",
    "CRUDService",
    "CallbackWithParam",
    "DbSession",
    "DbSessionFactory",
    "FilterFunction",
    "FilterParams",
    "HasId",
    "HasStatus",
    "HasUserId",
    "Headers",
    "JsonDict",
    "ModelT",
    "PermissionCheck",
    "QueryParams",
    "T",
    "ValueCallback",
    "VoidCallback",
]
