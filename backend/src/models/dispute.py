from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import DisputeStatus, UserRole
from backend.src.core.database import Base
from backend.src.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from .courier import Courier
    from .order import Order
    from .shop import Shop


class Dispute(TimestampMixin, Base):
    __tablename__ = "disputes"
    __repr_attrs__ = ("id", "status", "order_id")

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True, index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    courier_id: Mapped[int | None] = mapped_column(ForeignKey("couriers.id"))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[DisputeStatus] = mapped_column(
        Enum(DisputeStatus), default=DisputeStatus.OPEN, index=True
    )
    created_by_role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    admin_notes: Mapped[str | None] = mapped_column(Text, max_length=1000)
    resolution_notes: Mapped[str | None] = mapped_column(Text, max_length=1000)
    resolved_at: Mapped[datetime | None] = mapped_column()

    order: Mapped[Order] = relationship(back_populates="dispute", uselist=False)
    shop: Mapped[Shop] = relationship(back_populates="disputes")
    courier: Mapped[Courier | None] = relationship(back_populates="disputes")
