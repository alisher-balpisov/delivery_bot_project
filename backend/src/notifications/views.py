from fastapi import APIRouter

from backend.src.auth.dependencies import RequireAdmin

from .schemas import (
    BulkNotificationRequest,
    NotificationRequest,
    NotificationResponse,
    OrderUpdateNotificationRequest,
)
from .service import send_telegram_message

router = APIRouter()


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    notification: NotificationRequest,
    current_user: RequireAdmin,
) -> NotificationResponse:
    success = await send_telegram_message(notification)
    return NotificationResponse(
        success=success, sent=1 if success else 0, failed=0 if success else 1
    )


@router.post("/send-bulk", response_model=NotificationResponse)
async def send_bulk_notifications(
    request: BulkNotificationRequest,
    current_user: RequireAdmin,
) -> NotificationResponse:
    sent = 0
    failed = 0
    for notification in request.notifications:
        if await send_telegram_message(notification):
            sent += 1
        else:
            failed += 1
    return NotificationResponse(success=failed == 0, sent=sent, failed=failed)


@router.post("/send-order-update", response_model=NotificationResponse)
async def send_order_update_notification(
    request: OrderUpdateNotificationRequest,
    current_user: RequireAdmin,
) -> NotificationResponse:
    text = request.text or f"Обновление по заказу #{request.order_id}"
    notification = NotificationRequest(telegram_id=request.telegram_id, text=text)
    success = await send_telegram_message(notification)
    return NotificationResponse(
        success=success, sent=1 if success else 0, failed=0 if success else 1
    )


@router.post("/test-notification", response_model=NotificationResponse)
async def send_test_notification(current_user: RequireAdmin) -> NotificationResponse:
    notification = NotificationRequest(
        telegram_id=current_user.telegram_id,
        text="Тестовое уведомление Delivery Bot",
    )
    success = await send_telegram_message(notification)
    return NotificationResponse(
        success=success, sent=1 if success else 0, failed=0 if success else 1
    )
