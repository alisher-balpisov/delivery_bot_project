from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base

if TYPE_CHECKING:
    from .courier import Courier
    from .order import Order
    from .shop import Shop


class CourierRating(Base):
    __tablename__ = "courier_ratings"
    __repr_attrs__ = ("order_id", "courier_id", "rating")

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True, nullable=False)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), nullable=False)
    courier_id: Mapped[int] = mapped_column(
        ForeignKey("couriers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    rating: Mapped[int | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Связи
    order: Mapped[Order] = relationship(back_populates="rating")
    shop: Mapped[Shop] = relationship(back_populates="ratings_given")
    courier: Mapped[Courier] = relationship(back_populates="ratings_received")
