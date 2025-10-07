from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import OrderStatus, OrderType, SpecialOrderType
from backend.src.core.database import Base
from backend.src.models.courier_rating import CourierRating
from backend.src.models.order_history import OrderHistory

if TYPE_CHECKING:
    from .courier import Courier
    from .dispute import Dispute
    from .shop import Shop


class Order(Base):
    __tablename__ = "orders"
    __repr_attrs__ = ("shop_id", "status", "price")

    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), nullable=False, index=True)  # new
    courier_id: Mapped[int | None] = mapped_column(
        ForeignKey("couriers.id"), nullable=True, index=True
    )  # new

    status: Mapped[OrderStatus] = mapped_column(
        ENUM(OrderStatus, create_type=False),
        nullable=False,
        default=OrderStatus.pending,
        index=True,
    )  # new
    order_type: Mapped[OrderType] = mapped_column(
        ENUM(OrderType, create_type=False), nullable=False
    )  # new
    special_type: Mapped[SpecialOrderType | None] = mapped_column(
        ENUM(SpecialOrderType, create_type=False), nullable=True
    )  # new

    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    client_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_address: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_report_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Связи "родитель-ребёнок"
    shop: Mapped[Shop] = relationship(back_populates="orders")
    courier: Mapped[Courier] = relationship(back_populates="orders")

    # Связи один-к-одному
    history: Mapped[list[OrderHistory]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    dispute: Mapped[Dispute] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False
    )
    rating: Mapped[CourierRating] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False
    )
