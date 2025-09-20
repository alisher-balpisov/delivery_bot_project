from backend.src.common.enums import UserRole
from pydantic import BaseModel, ConfigDict


class UserDTO(BaseModel):
    """
    Data Transfer Object для данных пользователя.
    Обеспечивает типобезопасность и удобный доступ к данным.
    """

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    user_id: int | None = None
    telegram_id: int | None
    name: str | None = None
    role: UserRole = UserRole.GUEST
