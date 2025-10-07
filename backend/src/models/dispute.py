from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import DisputeResolutionType, DisputeStatus
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class Dispute(Base):
    __tablename__ = "disputes"
    __repr_attrs__ = ("order_id", "status")

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True, nullable=False)
    opened_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    fined_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(
        ENUM(DisputeStatus, create_type=False),
        default=DisputeStatus.pending_review,
        nullable=False,
        index=True,
    )  # new
    resolution_type: Mapped[DisputeResolutionType | None] = mapped_column(
        ENUM(DisputeResolutionType, create_type=False), nullable=True
    )  # new
    resolution_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    fine_amount: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Связи
    order: Mapped[Order] = relationship(back_populates="dispute")
    opened_by_user: Mapped[User] = relationship(
        back_populates="opened_disputes", foreign_keys=[opened_by_user_id]
    )
    fined_user: Mapped[User] = relationship(
        back_populates="fined_in_disputes", foreign_keys=[fined_user_id]
    )
