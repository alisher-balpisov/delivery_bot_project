from aiogram.filters import BaseFilter
from aiogram.types import Message
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

logger = get_logger(__name__)


class RoleFilter(BaseFilter):
    def __init__(self, roles: list[UserRole]) -> None:
        self.roles = roles

    async def __call__(self, event: Message, user_data: dict) -> bool:
        role = user_data.get("role")
        if role is None:
            logger.error("User role is None in user_data")
            return False

        if role not in self.roles:
            logger.error(f"User role {role} not in allowed roles {self.roles}")
            return False

        return True
