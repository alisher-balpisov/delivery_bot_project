import abc

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineQuery, Message, TelegramObject
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.dto import UserDTO

logger = get_logger(__name__)


class BaseAuthFilter(BaseFilter, abc.ABC):
    """
    Базовый абстрактный класс для фильтров авторизации.
    Ожидает аргумент 'user' (UserDTO) от Middleware.
    """

    @abc.abstractmethod
    async def _check_access(self, user: UserDTO) -> bool:
        pass

    def get_denial_message(self) -> str:
        return "Доступ запрещён"

    def get_required_roles(self) -> set[str] | None:
        return None

    async def __call__(self, event: TelegramObject, user: UserDTO) -> bool:
        return await self._check_access(user)

    def _log_access_denied(self, event: TelegramObject, user: UserDTO) -> None:
        event_type = type(event).__name__
        event_details = self._get_event_details(event)

        # Безопасное получение значения роли (на случай, если enum сложный)
        user_role_value = getattr(user.role, "value", str(user.role))

        base_msg = (
            f"{self.get_denial_message()} | "
            f"User: {user.telegram_id} (Role: {user_role_value}) | "
            f"Event: {event_type}({event_details})"
        )

        required = self.get_required_roles()
        if required:
            base_msg += f" | Required: {required}"

        logger.warning(base_msg)

    def _get_event_details(self, event: TelegramObject) -> str:
        """Извлекает детали события для логирования."""
        if isinstance(event, Message):
            # Обработка текста или кэпшона (для фото/файлов)
            text = event.text or event.caption or ""
            return f"text='{text[:30]}...'" if len(text) > 30 else f"text='{text}'"

        if isinstance(event, CallbackQuery):
            return f"data='{event.data}'"

        if isinstance(event, InlineQuery):
            return f"query='{event.query}'"

        return "no details"


class RoleFilter(BaseAuthFilter):
    """
    Фильтр доступа по списку разрешенных ролей.
    Использование: RoleFilter(UserRole.ADMIN, UserRole.MODERATOR)
    """

    def __init__(self, *roles: UserRole):
        if not roles:
            raise ValueError("RoleFilter требует хотя бы одну роль.")
        self.roles = set(roles)

    async def _check_access(self, user: UserDTO) -> bool:
        return user.role in self.roles

    def get_required_roles(self) -> set[str]:
        return {str(role.value) for role in self.roles}


class IsAuthenticatedFilter(BaseAuthFilter):
    """
    Допускает всех, кроме гостей.
    """

    async def _check_access(self, user: UserDTO) -> bool:
        return user.role != UserRole.GUEST

    def get_denial_message(self) -> str:
        return "Доступ запрещён (Unauthenticated)"
