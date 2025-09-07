"""
API роуты для управления уведомлениями.

Предоставляет REST API для отправки уведомлений пользователям.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.core.database import get_db
from src.models.user import User
from src.notifications.service import NotificationService, notification_service
from src.schemas.notification import (
    NotificationBulkRequest,
    NotificationBulkResponse,
    NotificationOrderUpdateRequest,
    NotificationResponse,
    NotificationSendRequest,
)

# Создаем новый router
router = APIRouter()


async def get_notification_service() -> NotificationService:
    """
    Получить сервис уведомлений.
    """
    # TODO: Здесь можно инициализировать с ботом из app.state
    return notification_service


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    """
    Получить пользователя по ID.
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Пользователь с ID {user_id} не найден")
    return user


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    request: NotificationSendRequest,
    db: AsyncSession = Depends(get_db),
    notification_svc: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    """
    Отправка уведомления конкретному пользователю.
    """
    user = await get_user_by_id(db, request.user_id)

    success = await notification_svc.send_notification(
        user=user,
        message=request.message,
        parse_mode="HTML",  # Можно делать динамическим
    )

    return {
        "success": success,
        "user_id": request.user_id,
        "message": "Уведомление отправлено успешно"
        if success
        else "Не удалось отправить уведомление",
    }


@router.post("/send-order-update")
async def send_order_update_notification(
    request: NotificationOrderUpdateRequest,
    db: AsyncSession = Depends(get_db),
    notification_svc: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    """
    Отправка уведомления об изменении статуса заказа.
    """
    user = await get_user_by_id(db, request.user_id)

    success = await notification_svc.notify_order_status_changed(
        user=user,
        order_id=request.order_id,
        new_status=request.new_status,
    )

    return {
        "success": success,
        "user_id": request.user_id,
        "order_id": request.order_id,
        "status": request.new_status,
    }


@router.post("/send-bulk", response_model=NotificationBulkResponse)
async def send_bulk_notifications(
    request: NotificationBulkRequest,
    db: AsyncSession = Depends(get_db),
    notification_svc: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    """
    Массовая отправка уведомлений нескольким пользователям.
    """
    # Получаем всех пользователей
    result = await db.execute(select(User).where(User.id.in_(request.user_ids)))
    users = result.scalars().all()

    # Проверяем что все пользователи найдены
    found_ids = {user.id for user in users}
    missing_ids = set(request.user_ids) - found_ids

    if missing_ids:
        raise HTTPException(status_code=400, detail=f"Пользователи не найдены: {list(missing_ids)}")

    # Формируем сообщение
    full_message = f"<b>{request.title}</b>\n\n{request.message}"

    bulk_tasks = await notification_svc.send_bulk_notifications(
        users=users,
        message=full_message,
        parse_mode="HTML",  # Можно делать настраиваемым
    )

    sent_count = sum(1 for success in bulk_tasks.values() if bulk_tasks[success])
    results = [
        {
            "success": bulk_tasks[str(user_id)],
            "user_id": int(user_id),
            "message": None,
        }
        for user_id in bulk_tasks
    ]

    return {
        "total_sent": sent_count,
        "total_failed": len(users) - sent_count,
        "results": results,
    }


@router.post("/test-notification")
async def send_test_notification(
    db: AsyncSession = Depends(get_db),
    notification_svc: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    """
    Тестовая отправка уведомления (для отладки).
    """
    # Получаем первого пользователя
    user_result = await db.execute(select(User).limit(1))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Нет пользователей в системе")

    success = await notification_svc.notify_system_message(
        user=user,
        title="Тестовое уведомление",
        content="Это тестовое уведомление для проверки работы системы уведомлений.",
        priority="low",
    )

    return {
        "success": success,
        "user_id": user.id,
        "message": "Тестовое уведомление отправлено",
    }
