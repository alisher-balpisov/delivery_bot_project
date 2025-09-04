from pydantic import BaseModel, ConfigDict


class CourierBase(BaseModel):
    is_active: bool = False
    max_orders: int = 5

    model_config = ConfigDict(from_attributes=True)


class CourierCreate(CourierBase):
    pass


class CourierUpdate(BaseModel):
    is_active: bool | None = None
    max_orders: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CourierResponse(CourierBase):
    id: int
    user_id: int
    current_orders: int

    model_config = ConfigDict(from_attributes=True)
