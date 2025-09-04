from __future__ import annotations

import html
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from src.common.enums import DisputeStatus, UserRole

from .order import OrderRead


class DisputeBase(BaseModel):
    """Базовая схема для спора."""

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
        """Валидация и санитизация описания."""
        if v:
            v = html.escape(v.strip())
            if len(v.split()) < 3:
                raise ValueError("Описание должно содержать минимум 3 слова")
        return v


class DisputeCreate(DisputeBase):
    """Схема для создания нового спора."""

    order_id: int = Field(..., gt=0, description="ID заказа")
    created_by_role: UserRole

    @field_validator("order_id")
    @classmethod
    def validate_order_id(cls, v: int) -> int:
        """Проверка корректности ID заказа."""
        if v <= 0:
            raise ValueError("ID заказа должен быть положительным числом")
        return v


class DisputeUpdate(BaseModel):
    """Схема для обновления спора (администратором)."""

    status: DisputeStatus | None = None
    admin_notes: str | None = Field(None, max_length=1000, description="Заметки администратора")
    resolution_notes: str | None = Field(
        None, max_length=1500, description="Описание решения спора"
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> DisputeUpdate:
        """Проверка логики разрешения спора."""
        if self.status == DisputeStatus.RESOLVED and not self.resolution_notes:
            raise ValueError("При закрытии спора необходимо указать resolution_notes")
        return self


class DisputeRead(DisputeBase):
    """Схема для чтения данных спора."""

    id: int
    status: DisputeStatus
    created_by_role: UserRole
    order: OrderRead
    admin_notes: str | None = None
    resolution_notes: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "description": "Товар пришёл с дефектом",
                "status": "OPEN",
                "created_by_role": "CUSTOMER",
                "created_at": "2024-01-01T10:00:00",
                "resolved_at": None,
            }
        },
    )

    @model_validator(mode="after")
    def validate_dates(self) -> DisputeRead:
        """Проверка корректности дат."""
        if self.resolved_at and self.resolved_at < self.created_at:
            raise ValueError("Дата разрешения не может быть раньше даты создания")
        return self


class DisputeResponse(DisputeBase):
    """Схема для ответа с данными спора."""

    id: int
    order_id: int
    courier_id: int
    shop_id: int
    status: DisputeStatus
    created_by_role: UserRole
    admin_notes: str | None = None
    resolution_notes: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DisputeList(BaseModel):
    """Схема для списка споров с пагинацией."""

    items: list[DisputeRead]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=100)

    @property
    def pages(self) -> int:
        """Общее количество страниц."""
        return (self.total + self.per_page - 1) // self.per_page if self.per_page > 0 else 0

    model_config = ConfigDict(from_attributes=True)
