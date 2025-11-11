from __future__ import annotations

import html
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.src.common.constants import PaginatedResponse
from backend.src.common.enums import DisputeStatus, UserRole
from backend.src.models.dispute import Dispute


class DisputeBase(BaseModel):
    """Базовая схема для спора с общими полями."""

    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Детальное описание проблемы",
        examples=["Товар пришёл повреждённым, упаковка была нарушена"],
    )

    @field_validator("description")
    @classmethod
    def validate_and_sanitize_description(cls, v: str) -> str:
        """
        Валидация и санитизация описания.

        Проверяет минимальное количество слов и экранирует HTML.
        """
        if not v:
            raise ValueError("Описание не может быть пустым")

        # Санитизация HTML
        sanitized = html.escape(v.strip())

        # Проверка минимального количества слов
        word_count = len(sanitized.split())
        if word_count < 3:
            raise ValueError(f"Описание должно содержать минимум 3 слова (сейчас: {word_count})")

        return sanitized


class DisputeCreate(DisputeBase):
    """Схема для создания нового спора."""

    order_id: int = Field(..., gt=0, description="ID заказа, по которому открывается спор")


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


class DisputeResponse(DisputeBase):
    """Полная схема ответа с данными спора."""

    id: int
    order_id: int
    courier_id: int
    shop_id: int
    status: DisputeStatus
    created_by_role: UserRole
    resolution_notes: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DisputeListItem(BaseModel):
    """Схема для отображения спора в списке (краткая информация)."""

    id: int
    order_id: int
    shop_id: int
    shop_name: str | None = Field(None, description="Название магазина")
    courier_id: int
    courier_name: str | None = Field(None, description="ФИО курьера")
    status: DisputeStatus
    created_by_role: UserRole
    description: str = Field(..., description="Короткое описание проблемы")
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DisputeFilters(BaseModel):
    """Фильтры для списка споров."""

    status: DisputeStatus | None = Field(None, description="Фильтр по статусу")
    shop_id: int | None = Field(None, gt=0, description="Фильтр по ID магазина")
    courier_id: int | None = Field(None, gt=0, description="Фильтр по ID курьера")
    created_by_role: UserRole | None = Field(None, description="Фильтр по роли создателя")


DisputeListResponse = PaginatedResponse[DisputeListItem]


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
