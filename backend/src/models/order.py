from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, CheckConstraint, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import OrderStatus, OrderType
from backend.src.core.database import Base
from backend.src.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from .courier import Courier
    from .dispute import Dispute
    from .photo_report import PhotoReport
    from .shop import Shop
    from .zone import Zone


class Order(TimestampMixin, Base):
    """
    Представляет заказ в таблице `orders`.
    """

    __tablename__ = "orders"
    __repr_attrs__ = ("status", "shop_id", "courier_id")

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    courier_id: Mapped[int | None] = mapped_column(ForeignKey("couriers.id"))

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.CREATED, index=True
    )
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType), default=OrderType.NORMAL)
    description: Mapped[str | None] = mapped_column(Text)
    recipient_name: Mapped[str | None] = mapped_column(String(100))
    recipient_phone: Mapped[str] = mapped_column(String(20))
    recipient_address: Mapped[str] = mapped_column(String(255))
    delivery_time: Mapped[datetime | None] = mapped_column()
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2))
    pickup_address: Mapped[str] = mapped_column(String(255))
    courier_notes: Mapped[str | None] = mapped_column(Text)
    completion_notes: Mapped[str | None] = mapped_column(Text)

    is_fragile: Mapped[bool] = mapped_column(default=False)
    is_bulky: Mapped[bool] = mapped_column(default=False)
    special_reason: Mapped[str | None] = mapped_column(Text)

    zone_addon: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=Decimal("0.00"))
    rush_hour_addon: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=Decimal("0.00"))

    courier_rating: Mapped[int | None] = mapped_column()
    courier_feedback: Mapped[str | None] = mapped_column(Text)

    accepted_at: Mapped[datetime | None] = mapped_column()
    delivered_at: Mapped[datetime | None] = mapped_column()
    confirmed_at: Mapped[datetime | None] = mapped_column()
    autoconfirmed_at: Mapped[datetime | None] = mapped_column()

    shop: Mapped[Shop] = relationship(back_populates="orders")
    courier: Mapped[Courier | None] = relationship(back_populates="orders")
    zone: Mapped[Zone] = relationship(back_populates="orders")
    dispute: Mapped[Dispute | None] = relationship(
        back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    photo_reports: Mapped[list[PhotoReport]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "courier_rating IS NULL OR (courier_rating >= 1 AND courier_rating <= 5)",
            name="check_courier_rating_range",
        ),
        # Индексы для оптимизации запросов
        Index("idx_orders_shop_id", "shop_id"),
        Index("idx_orders_courier_id", "courier_id"),
        Index("idx_orders_status_created", "status", "created_at"),
    )
