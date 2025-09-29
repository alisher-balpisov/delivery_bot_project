from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.mixins import UpdatedAtMixin

if TYPE_CHECKING:
    from .dispute import Dispute
    from .order import Order
    from .user import User


class Courier(UpdatedAtMixin, Base):
    __tablename__ = "couriers"
    __repr_attrs__ = ("id", "user_id", "is_active")

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    is_active: Mapped[bool] = mapped_column(default=False)
    current_orders: Mapped[int] = mapped_column(default=0)
    max_orders: Mapped[int] = mapped_column(default=5)

    __table_args__ = (
        CheckConstraint("current_orders >= 0", name="check_current_orders_positive"),
        CheckConstraint("current_orders <= max_orders", name="check_max_orders_limit"),
        CheckConstraint("max_orders > 0", name="check_max_orders_positive"),
    )

    user: Mapped[User] = relationship(back_populates="courier", uselist=False)
    orders: Mapped[list[Order]] = relationship(back_populates="courier")
    disputes: Mapped[list[Dispute]] = relationship(back_populates="courier")
