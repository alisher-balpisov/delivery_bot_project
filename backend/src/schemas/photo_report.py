from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PhotoReportBase(BaseModel):
    """Базовая схема для фотоотчета."""

    file_id: str = Field(..., max_length=255, description="ID файла из Telegram")
    description: str | None = Field(None, description="Дополнительное описание фото")

    model_config = ConfigDict(from_attributes=True)


class PhotoReportCreate(PhotoReportBase):
    """Схема для создания фотоотчета."""

    order_id: int


class PhotoReportUpdate(BaseModel):
    """Схема для обновления фотоотчета."""

    file_id: str | None = None
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PhotoReportResponse(PhotoReportBase):
    """Схема для ответа с данными фотоотчета."""

    id: int
    order_id: int
    file_path: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PhotoReportListResponse(BaseModel):
    """Схема для списка фотоотчетов."""

    photo_reports: list[PhotoReportResponse]
    total: int
