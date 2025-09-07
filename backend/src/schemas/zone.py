from pydantic import BaseModel, ConfigDict, Field


class ZoneBase(BaseModel):
    name: str = Field(..., max_length=255)
    radius_km: int
    base_price: float

    model_config = ConfigDict(from_attributes=True)


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    name: str | None = None
    radius_km: int | None = None
    base_price: float | None = None

    model_config = ConfigDict(from_attributes=True)


class ZoneResponse(ZoneBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
