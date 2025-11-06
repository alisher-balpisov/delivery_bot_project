from backend.src.common.enums import UserStatus
from backend.src.common.utils.validaters import Phone
from pydantic import BaseModel, ConfigDict, Field

from .user import UserRead


class ShopBase(BaseModel):
    """Базовая схема для магазина."""

    name: str = Field(..., max_length=255)
    address: str | None = Field(None, max_length=255)

    model_config = ConfigDict(from_attributes=True)


class ShopCreate(ShopBase):
    """Схема для создания профиля магазина."""

    user_id: int


class ShopUpdate(BaseModel):
    """Схема для обновления магазина."""

    name: str | None = None
    address: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ShopRead(ShopBase):
    """Схема для чтения данных магазина."""

    id: int
    user: UserRead

    model_config = ConfigDict(from_attributes=True)


class ShopResponse(ShopBase):
    """Схема для ответа с данными магазина."""

    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class ShopRegistration(BaseModel):
    """
    Комплексная схема для регистрации магазина,
    включающая данные пользователя и магазина.
    """

    telegram_id: int
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=100)
    phone: Phone = Field(..., max_length=20)
    shop_name: str = Field(..., max_length=255)
    shop_address: str | None = Field(None, max_length=255)

    model_config = ConfigDict(from_attributes=True)


class ShopCardResponse(BaseModel):
    """
    Схема для ответа с данными карточки магазина и кнопками на основе роли пользователя.
    """

    id: int
    telegram_id: int
    username: str | None
    name: str | None
    status: UserStatus
    address: str | None
    address_link: str | None
    phone_numbers: list[str] | None

    model_config = ConfigDict(from_attributes=True)
