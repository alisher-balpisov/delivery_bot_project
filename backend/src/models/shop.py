from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base

if TYPE_CHECKING:
    from .courier_rating import CourierRating
    from .order import Order
    from .user import User


class Shop(Base):
    """
    Модель профиля магазина.

    Создается при регистрации пользователя с ролью "магазин".
    Содержит информацию о магазине и связь с его заказами.
    """

    __tablename__ = "shops"
    __repr_attrs__ = ("user_id", "name")

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="ID пользователя, связанного с профилем магазина",
    )
    name: Mapped[str] = mapped_column(
        String(255), index=True, nullable=False, comment="Название магазина"
    )
    address: Mapped[str] = mapped_column(String(512), nullable=False, comment="Адрес магазина")
    address_link: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="Ссылка на адрес магазина (например, Google Maps)"
    )
    phone_number: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)), nullable=False, comment="Контактные номера телефонов магазина"
    )

    # Связи
    user: Mapped[User] = relationship(back_populates="shop", uselist=False, lazy="joined")
    orders: Mapped[list[Order]] = relationship(back_populates="shop", lazy="selectin")
    ratings_given: Mapped[list[CourierRating]] = relationship(
        back_populates="shop", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="check_shop_name_not_empty"),
        CheckConstraint("length(trim(address)) > 0", name="check_shop_address_not_empty"),
        CheckConstraint("length(trim(address_link)) > 0", name="check_shop_address_link_not_empty"),
        CheckConstraint("cardinality(phone_number) > 0", name="check_shop_phone_number_not_empty"),
    )
