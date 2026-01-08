from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import DeliveryTimeType, OrderStatus, OrderType, SpecialOrderType
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
    special_type: Mapped[SpecialOrderType | None] = mapped_column(
        ENUM(
            SpecialOrderType,
            name="specialordertype",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )

    price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), nullable=False, comment="Стоимость доставки"
    )
    client_phone: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Телефон клиента (заказчика в магазине)"
    )
    recipient_address: Mapped[str] = mapped_column(Text, nullable=False, comment="Адрес получателя")
    recipient_phone: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Телефон получателя"
    )
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

    # Связи многие-к-одному (родительские)
    shop: Mapped[Shop] = relationship(back_populates="orders", lazy="selectin")
    courier: Mapped[Courier | None] = relationship(back_populates="orders", lazy="selectin")

    # Связи один-ко-многим и один-к-одному (дочерние)
    history: Mapped[list[OrderHistory]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    dispute: Mapped[Dispute | None] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False, lazy="select"
    )
    rating: Mapped[CourierRating | None] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False, lazy="select"
    )
    notes: Mapped[list[OrderNote]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(client_phone)) > 0", name="check_order_client_phone_not_empty"
        ),
        CheckConstraint(
            "length(trim(recipient_address)) > 0", name="check_order_recipient_address_not_empty"
        ),
        CheckConstraint(
            "length(trim(recipient_phone)) > 0", name="check_order_recipient_phone_not_empty"
        ),
        CheckConstraint("price > 0", name="check_price_positive"),
        CheckConstraint(
            (status != OrderStatus.COMPLETED) | (completed_at is not None),
            name="check_completed_at_if_completed",
        ),
        CheckConstraint(
            ((order_type == OrderType.REGULAR) & (special_type.is_(None)))
            | ((order_type == OrderType.SPECIAL) & (special_type.is_not(None))),
            name="check_special_type_logic",
        ),
        Index("ix_orders_shop_status", "shop_id", "status"),
        Index("ix_orders_courier_status", "courier_id", "status"),
        Index("ix_orders_delivery_type_status", "delivery_time_type", "status"),
        Index("ix_orders_status", "status"),
    )
