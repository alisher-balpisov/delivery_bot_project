from aiogram.filters import BaseFilter
from aiogram.types import Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.dto import UserDTO

logger = get_logger(__name__)


class RoleFilter(BaseFilter):
    def __init__(self, *roles: UserRole):
        self.roles = roles

    async def __call__(self, event: Message, user: UserDTO) -> bool:
        """
        Фильтр теперь принимает user: UserDTO напрямую от middleware.
        """
        if user is None:
            logger.warning("RoleFilter: UserDTO is None, access denied.")
            return False

        # Проверяем, что роль пользователя из DTO входит в список разрешенных ролей
        if user.role not in self.roles:
            logger.debug(
                f"Access denied for telegram_id={user.telegram_id}. "
                f"Required roles: {self.roles}, user role: {user.role}"
            )
            return False

        return True
