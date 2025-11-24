from pydantic import BaseModel, ConfigDict

from backend.src.common.enums import UserStatus


class ShopCardResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    name: str | None
    status: UserStatus
    address: str | None
    address_link: str | None
    phone_numbers: list[str] | None

    model_config = ConfigDict(from_attributes=True)


class ShopListItem(BaseModel):
    id: int
    name: str | None
    status: UserStatus
    telegram_id: int


class ShopListResponse(BaseModel):
    items: list[ShopListItem]
    total: int
    page: int
    pages: int
