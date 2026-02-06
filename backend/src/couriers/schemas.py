from pydantic import BaseModel, ConfigDict

from backend.src.common.enums import UserStatus


class CourierCardResponse(BaseModel):
    """
    Схема для ответа с данными карточки курьера и кнопками на основе роли пользователя.
    """

    id: int
    telegram_id: int | None
    username: str | None
    full_name: str | None
    status: UserStatus | None
    phone_numbers: list[str] | None
    photo_id: str | None = None
    is_active: bool
    rating: float | None = None

    model_config = ConfigDict(from_attributes=True)


class CourierShiftResponse(BaseModel):
    """Схема для ответа о статусе смены курьера."""

    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CourierListItem(BaseModel):
    """Схема элемента списка курьеров."""

    id: int
    full_name: str
    is_active: bool  # Статус смены (on shift)
    user_status: UserStatus  # Статус пользователя (active/inactive/blocked)

    model_config = ConfigDict(from_attributes=True)


class CourierListResponse(BaseModel):
    """Схема ответа со списком курьеров и пагинацией."""

    items: list[CourierListItem]
    total: int
    page: int
    size: int


class CourierSelectionItem(BaseModel):
    """Схема курьера для выбора магазином."""

    id: int
    full_name: str | None
    active_orders_count: int
    rating: float

    model_config = ConfigDict(from_attributes=True)
