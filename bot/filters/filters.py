import abc

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.dto import UserDTO

logger = get_logger(__name__)


class BaseAuthFilter(BaseFilter, abc.ABC):
    """
    Базовый абстрактный класс для фильтров, связанных с авторизацией.
    Явно зависит от UserDTO, предоставляемого фильтром UserDataFilter.
    """

    @abc.abstractmethod
    async def _check_access(self, user: UserDTO) -> bool:
        """
        Абстрактный метод, определяющий логику проверки доступа.
        Должен быть реализован в дочерних классах.
        """
        pass

    def get_denial_message(self) -> str:
        """Текст сообщения при отказе в доступе (для логирования)."""
        return "Доступ запрещён"

    def get_required_roles(self) -> set[str] | None:
        """Возвращает набор требуемых ролей (для логирования)."""
        return None

    async def __call__(self, event: TelegramObject, user: UserDTO) -> bool:
        """
        Основная логика фильтра:
        1. Проверяет доступ через _check_access.
        2. Если доступ запрещён — логирует информацию и возвращает False.
        """
        if await self._check_access(user):
            return True

        self._log_access_denied(event, user)
        return False

    def _log_access_denied(self, event: TelegramObject, user: UserDTO) -> None:
        """Централизованно логирует отказы в доступе."""
        event_type = type(event).__name__
        event_details = self._get_event_details(event)
        user_role_value = user.role.value
        message = self.get_denial_message()
        required_roles = self.get_required_roles()

        log_message = (
            f"{message} | Пользователь: {user.telegram_id} (Роль: {user_role_value}) | "
            f"Событие: {event_type}({event_details})"
        )
        if required_roles:
            log_message = (
                f"{message} | Пользователь: {user.telegram_id} (Роль: {user_role_value}) | "
                f"Требуемые роли: {required_roles} | Событие: {event_type}({event_details})"
            )

        logger.warning(log_message)

    def _get_event_details(self, event: TelegramObject) -> str:
        """Извлекает детали события для логирования."""
        if isinstance(event, Message) and event.text:
            text = event.text
            return f"текст='{text[:30]}...'" if len(text) > 30 else f"текст='{text}'"
        if isinstance(event, CallbackQuery) and event.data:
            return f"данные='{event.data}'"
        return "нет деталей"


class RoleFilter(BaseAuthFilter):
    """Фильтр доступа по конкретным ролям пользователя."""

    def __init__(self, *roles: UserRole):
        if not roles:
            raise ValueError("RoleFilter требует хотя бы одну роль.")
        self.roles: set[UserRole] = set(roles)
        logger.debug(f"RoleFilter инициализирован с ролями: {[role.value for role in self.roles]}")

    async def _check_access(self, user: UserDTO) -> bool:
        return user.role in self.roles

    def get_required_roles(self) -> set[str]:
        required = {role.value for role in self.roles}
        logger.debug(f"RoleFilter get_required_roles: {required}")
        return required


class IsAuthenticatedFilter(BaseAuthFilter):
    """Фильтр доступа для всех аутентифицированных пользователей (не гостей)."""

    async def _check_access(self, user: UserDTO) -> bool:
        return user.role != UserRole.GUEST

    def get_denial_message(self) -> str:
        return "Доступ запрещён (пользователь не аутентифицирован)"
