from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import ChangeType
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class OrderHistory(Base):
    __tablename__ = "order_history"
    __repr_attrs__ = ("order_id", "change_type")

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    change_type: Mapped[ChangeType] = mapped_column(
        ENUM(ChangeType, create_type=False), nullable=False
    )  # new
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Связи
    order: Mapped[Order] = relationship(back_populates="history")
    changed_by_user: Mapped[User] = relationship(back_populates="order_history_entries")
