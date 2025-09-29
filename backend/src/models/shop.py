from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from .dispute import Dispute
    from .order import Order
    from .user import User


class Shop(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "shops"
    __repr_attrs__ = ("id", "name", "user_id")

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="shop", uselist=False)
    orders: Mapped[list[Order]] = relationship(back_populates="shop")
    disputes: Mapped[list[Dispute]] = relationship(back_populates="shop")

    __table_args__ = (
        Index("idx_shops_user_id", "user_id"),
        Index("idx_shops_is_deleted", "is_deleted"),
    )
