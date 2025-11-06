# backend/src/schemas/order_history.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrderHistoryResponse(BaseModel):
    id: int
    order_id: int
    status: str
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)
