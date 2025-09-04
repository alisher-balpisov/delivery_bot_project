from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from src.common.enums import UserRole


class RegistrationCodeBase(BaseModel):
    code: str = Field(..., max_length=20)
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class RegistrationCodeCreate(RegistrationCodeBase):
    pass


class RegistrationCodeResponse(RegistrationCodeBase):
    id: int
    is_used: bool
    user_id: int | None = None
    created_at: datetime
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
