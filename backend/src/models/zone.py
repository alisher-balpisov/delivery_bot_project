from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base

if TYPE_CHECKING:
    from .order import Order


class Zone(Base):
    """
    Представляет зону доставки в таблице `zones`.
    """

    __tablename__ = "zones"
    __repr_attrs__ = ("name", "base_price")

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    radius_km: Mapped[int] = mapped_column()
    base_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=Decimal("3000.00"))

    orders: Mapped[list[Order]] = relationship(back_populates="zone")

    __table_args__ = (
        CheckConstraint("radius_km > 0", name="check_radius_positive"),
        CheckConstraint("base_price >= 0", name="check_base_price_non_negative"),
    )
