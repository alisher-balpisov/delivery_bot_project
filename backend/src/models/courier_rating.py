from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base

if TYPE_CHECKING:
    from .courier import Courier
    from .order import Order
    from .shop import Shop


class CourierRating(Base):
    """
    Модель рейтинга курьера от магазина за выполненный заказ.

    Каждый заказ может иметь только один рейтинг.
    Рейтинг выставляется магазином курьеру после завершения доставки.
    """

    __tablename__ = "courier_ratings"
    __repr_attrs__ = ("order_id", "courier_id", "rating")

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        unique=True,
        nullable=False,
        index=True,
        comment="ID заказа, за который выставлен рейтинг",
    )
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id"),
        nullable=False,
        index=True,
        comment="ID магазина, который выставил рейтинг",
    )
    courier_id: Mapped[int] = mapped_column(
        ForeignKey("couriers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID курьера, которому выставлен рейтинг",
    )

    rating: Mapped[int | None] = mapped_column(
        nullable=True, comment="Рейтинг от 1 до 5 (NULL если еще не выставлен)"
    )
    comment: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Комментарий к рейтингу"
    )

    # Связи
    order: Mapped[Order] = relationship(back_populates="rating", lazy="joined")
    shop: Mapped[Shop] = relationship(back_populates="ratings_given", lazy="joined")
    courier: Mapped[Courier] = relationship(back_populates="ratings_received", lazy="joined")

    __table_args__ = (
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="check_rating_range"),
        CheckConstraint(
            "comment IS NULL OR length(trim(comment)) > 0", name="check_comment_not_empty"
        ),
        Index("ix_courier_ratings_courier_id_rating", "courier_id", "rating"),
    )
