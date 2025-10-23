from typing import Any

from backend.src.auth.dependencies import RequireAdmin
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.models.user import User
from backend.src.notifications import service
from backend.src.notifications.service import Notification
from backend.src.schemas.notification import (
    NotificationBulkRequest,
    NotificationBulkResponse,
    NotificationResponse,
    NotificationSendRequest,
)
from fastapi import APIRouter, HTTPException
from sqlalchemy.future import select

router = APIRouter()

logger = get_logger(__name__)


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    request: NotificationSendRequest,
    current_user: RequireAdmin,
    db: DbSession,
    notification_svc: Notification,
) -> dict[str, Any]:
    """
    Отправка уведомления конкретному пользователю.
    Доступно только администраторам.
    """

    logger.info(f"Admin {current_user.id} sending notification to user {request.user_id}")
    user = await service.get_user_by_id(db, request.user_id)

    success = await notification_svc.send_notification(
        user=user,
        message=request.message,
    )

    return {
        "success": success,
        "user_id": request.user_id,
        "message": "Уведомление отправлено успешно"
        if success
        else "Не удалось отправить уведомление",
    }


@router.post("/send-bulk", response_model=NotificationBulkResponse)
async def send_bulk_notifications(
    request: NotificationBulkRequest,
    current_user: RequireAdmin,
    db: DbSession,
    notification_svc: Notification,
) -> dict[str, Any]:
    """
    Массовая отправка уведомлений нескольким пользователям.
    Доступно только администраторам.
    """
    result = await db.execute(select(User).where(User.id.in_(request.user_ids)))
    users = result.scalars().all()

    found_ids = {user.id for user in users}
    missing_ids = set(request.user_ids) - found_ids
    if missing_ids:
        raise HTTPException(status_code=400, detail=f"Пользователи не найдены: {list(missing_ids)}")

    full_message = f"<b>{request.title}</b>\n\n{request.message}"
    bulk_results = await notification_svc.send_bulk_notifications(
        users=users,
        message=full_message,
    )

    sent_count = sum(1 for success in bulk_results.values() if success)
    results_list = [
        {"success": success, "user_id": int(user_id), "message": None}
        for user_id, success in bulk_results.items()
    ]

    return {
        "total_sent": sent_count,
        "total_failed": len(users) - sent_count,
        "results": results_list,
    }


@router.post("/test-notification", response_model=dict)
async def send_test_notification(
    current_user: RequireAdmin,
    notification_svc: Notification,
) -> dict[str, Any]:
    """
    Тестовая отправка уведомления самому себе (администратору).
    """
    success = await notification_svc.notify_system_message(
        user=current_user,
        title="Тестовое уведомление",
        content="Это тестовое уведомление для проверки работы системы.",
        priority="low",
    )

    return {
        "success": success,
        "user_id": current_user.id,
        "message": "Тестовое уведомление отправлено",
    }
