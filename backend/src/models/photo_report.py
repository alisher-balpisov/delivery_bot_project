from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.mixins import CreatedAtMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from .order import Order


class PhotoReport(CreatedAtMixin, SoftDeleteMixin, Base):
    __tablename__ = "photo_reports"
    __repr_attrs__ = ("id", "order_id")

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    file_id: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    order: Mapped[Order] = relationship(back_populates="photo_reports")
