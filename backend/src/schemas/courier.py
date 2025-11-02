from backend.src.common.enums import UserStatus
from backend.src.common.utils import Phone
from pydantic import BaseModel, ConfigDict, Field


class CourierBase(BaseModel):
    is_active: bool = False
    max_orders: int = 5

    model_config = ConfigDict(from_attributes=True)


class CourierUpdate(BaseModel):
    is_active: bool | None = None
    max_orders: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CourierResponse(CourierBase):
    id: int
    user_id: int
    current_orders: int

    model_config = ConfigDict(from_attributes=True)


class CourierRead(BaseModel):
    """Схема для чтения данных о курьере."""

    user_id: int
    full_name: str
    phone_number: list[str]
    photo_id: str | None = None
    is_active: bool = Field(..., description="Статус активности (на смене / не на смене)")

    model_config = ConfigDict(from_attributes=True)


class CourierRegistration(BaseModel):
    """
    Комплексная схема для регистрации курьера,
    включающая данные пользователя.
    """

    telegram_id: int
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=100)
    phone: Phone

    model_config = ConfigDict(from_attributes=True)


class CourierCardResponse(BaseModel):
    """
    Схема для ответа с данными карточки курьера и кнопками на основе роли пользователя.
    """

    id: int
    telegram_id: int | None
    username: str | None
    full_name: str
    status: UserStatus | None
    phone_numbers: list
    photo_id: str | None = None
    is_active: bool
    rating: float | None = None


class CourierShiftResponse(BaseModel):
    """Схема для ответа о статусе смены курьера."""

    is_active: bool

    model_config = ConfigDict(from_attributes=True)
