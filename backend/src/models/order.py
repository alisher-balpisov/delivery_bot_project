from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, or_
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import DeliveryTimeType, OrderStatus, OrderType
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .courier import Courier
    from .courier_rating import CourierRating
    from .dispute import Dispute
    from .order_history import OrderHistory
    from .order_note import OrderNote
    from .shop import Shop


class Order(Base):
    """
    Модель заказа.

    Основная сущность системы, представляющая заказ от магазина,
    который должен быть доставлен курьером.
    """

    __tablename__ = "orders"
    __repr_attrs__ = ("shop_id", "courier_id", "status", "price")

    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id"), nullable=False, index=True, comment="ID магазина, создавшего заказ"
    )
    courier_id: Mapped[int | None] = mapped_column(
        ForeignKey("couriers.id"),
        nullable=True,
        index=True,
        comment="ID назначенного курьера (NULL если еще не назначен)",
    )

    status: Mapped[OrderStatus] = mapped_column(
        ENUM(
            OrderStatus,
            name="orderstatus",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=OrderStatus.PENDING,
    )
    order_type: Mapped[OrderType] = mapped_column(
        ENUM(
            OrderType,
            name="ordertype",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=OrderType.REGULAR,
    )

    price: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Стоимость доставки")

    delivery_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, comment="Желаемое время доставки"
    )
    delivery_time_type: Mapped[DeliveryTimeType] = mapped_column(
        ENUM(
            DeliveryTimeType,
            name="deliverytimetype",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DeliveryTimeType.TODAY,
        index=True,
        comment="Тип времени доставки (asap/today/scheduled)",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Описание/комментарии к заказу"
    )
    photo_report_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="ID фото-отчета о доставке в Telegram"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Дата и время завершения заказа"
    )

    # Связи
    shop: Mapped[Shop] = relationship(back_populates="orders", lazy="noload")
    courier: Mapped[Courier | None] = relationship(back_populates="orders", lazy="noload")

    history: Mapped[list[OrderHistory]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="noload"
    )
    disputes: Mapped[list[Dispute]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="noload"
    )
    rating: Mapped[CourierRating | None] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False, lazy="noload"
    )
    notes: Mapped[list[OrderNote]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="noload"
    )

    __table_args__ = (
        CheckConstraint("price > 0", name="check_price_positive"),
        CheckConstraint(
            or_(status != OrderStatus.COMPLETED, completed_at.is_not(None)),
            name="check_completed_at_if_completed",
        ),
        Index("ix_orders_shop_status", "shop_id", "status"),
        Index("ix_orders_courier_status", "courier_id", "status"),
        Index("ix_orders_delivery_type_status", "delivery_time_type", "status"),
        Index("ix_orders_status", "status"),
    )
