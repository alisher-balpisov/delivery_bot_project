from __future__ import annotations

import html
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.src.common.enums import DisputeStatus, UserRole
from backend.src.models.dispute import Dispute


class DisputeCreate(BaseModel):
    """Схема для создания нового спора."""

    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Детальное описание проблемы",
    )
    order_id: int = Field(..., gt=0, description="ID заказа, по которому открывается спор")

    @field_validator("description")
    @classmethod
    def validate_and_sanitize_description(cls, v: str) -> str:
        """Валидация и санитизация описания."""
        if not v:
            raise ValueError("Описание не может быть пустым")
        sanitized = html.escape(v.strip())
        word_count = len(sanitized.split())
        if word_count < 3:
            raise ValueError(f"Описание должно содержать минимум 3 слова (сейчас: {word_count})")
        return sanitized


class DisputeUpdate(BaseModel):
    """
    Схема для обновления спора администратором.

    Все поля опциональны для частичного обновления.
    """

    status: DisputeStatus | None = Field(None, description="Новый статус спора")
    resolution_notes: str | None = Field(
        None,
        min_length=10,
        max_length=1500,
        description="Описание решения спора",
    )

    @field_validator("resolution_notes")
    @classmethod
    def sanitize_resolution_notes(cls, v: str | None) -> str | None:
        """Санитизация заметок о решении."""
        if v:
            return html.escape(v.strip())
        return v

    @model_validator(mode="after")
    def validate_resolution_logic(self) -> DisputeUpdate:
        """
        Проверка бизнес-логики разрешения спора.

        При закрытии спора обязательно указать resolution_notes.
        """
        if self.status == DisputeStatus.RESOLVED and not self.resolution_notes:
            raise ValueError(
                "При переводе спора в статус RESOLVED обязательно указать resolution_notes"
            )
        return self


class DisputeResponse(BaseModel):
    """Полная схема ответа с данными спора."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    courier_id: int
    shop_id: int
    status: DisputeStatus
    created_by_role: UserRole
    description: str
    resolution_comment: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DisputeCardResponse(BaseModel):
    """Схема для отображения спора в списке (карточка спора для админа)."""

    id: int
    order_id: int
    shop_id: int | None
    shop_name: str | None
    courier_id: int
    courier_name: str | None
    status: DisputeStatus
    opened_by_role: UserRole
    opened_by_user_id: int
    description: str
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_dispute(cls, dispute: Dispute) -> DisputeCardResponse:
        """Создаёт объект ответа на основе модели Dispute."""

        if not dispute.order.courier_id:
            raise ValueError("Courier not found")

        return cls(
            id=dispute.id,
            order_id=dispute.order_id,
            shop_id=dispute.order.shop_id,
            shop_name=getattr(dispute.order.shop, "name", None),
            courier_id=dispute.order.courier_id,
            courier_name=getattr(dispute.order.courier, "full_name", None),
            status=dispute.status,
            opened_by_role=dispute.opened_by_user.role,
            opened_by_user_id=dispute.opened_by_user_id,
            description=dispute.description,
            created_at=dispute.created_at,
            resolved_at=dispute.resolved_at,
        )
