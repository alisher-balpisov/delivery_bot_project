from pydantic import BaseModel, Field


class NotificationRequest(BaseModel):
    telegram_id: int = Field(..., description="Telegram ID получателя")
    text: str = Field(..., min_length=1, max_length=4096)
    parse_mode: str | None = "HTML"
    disable_web_page_preview: bool = True


class BulkNotificationRequest(BaseModel):
    notifications: list[NotificationRequest] = Field(default_factory=list, max_length=100)


class OrderUpdateNotificationRequest(BaseModel):
    telegram_id: int
    order_id: int
    text: str | None = None


class NotificationResponse(BaseModel):
    success: bool
    sent: int = 0
    failed: int = 0
    detail: str | None = None
