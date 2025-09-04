"""
Схемы для уведомлений.

Определяет модели данных для отправки и обработки уведомлений.
"""

from pydantic import BaseModel, ConfigDict, Field


class NotificationBase(BaseModel):
    """Базовая схема для отправки уведомлений."""

    title: str = Field(..., max_length=100, description="Заголовок уведомления")
    message: str = Field(..., description="Текст уведомления")
    priority: str = Field("normal", description="Приоритет уведомления (high, normal, low)")

    model_config = ConfigDict(from_attributes=True)


class NotificationSendRequest(NotificationBase):
    """Схема для запроса отправки уведомления."""

    user_id: int = Field(..., description="ID пользователя для уведомления")


class NotificationOrderUpdateRequest(BaseModel):
    """Схема для уведомления об изменении статуса заказа."""

    user_id: int = Field(..., description="ID пользователя")
    order_id: int = Field(..., description="ID заказа")
    new_status: str = Field(..., description="Новый статус заказа")
    additional_info: str | None = Field(None, description="Дополнительная информация")


class NotificationBulkRequest(BaseModel):
    """Схема для массовой отправки уведомлений."""

    user_ids: list[int] = Field(..., description="Список ID пользователей")
    title: str = Field(..., max_length=100, description="Заголовок уведомления")
    message: str = Field(..., description="Текст уведомления")
    priority: str = Field("normal", description="Приоритет уведомления")


class NotificationResponse(BaseModel):
    """Схема для ответа после отправки уведомления."""

    success: bool = Field(..., description="Успешно ли отправлено уведомление")
    user_id: int = Field(..., description="ID пользователя")
    message: str | None = Field(None, description="Сообщение о результате")


class NotificationBulkResponse(BaseModel):
    """Схема для ответа после массовой отправки уведомлений."""

    total_sent: int = Field(..., description="Количество успешно отправленных уведомлений")
    total_failed: int = Field(..., description="Количество неудачных отправок")
    results: list[NotificationResponse] = Field(..., description="Детальные результаты по каждому пользователю")
