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

    class Config:
        orm_mode = True


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
    name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=20)
    shop_name: str = Field(..., max_length=255)
    shop_address: str | None = Field(None, max_length=255)
