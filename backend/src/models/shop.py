from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.courier_rating import CourierRating

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class Shop(Base):
    __tablename__ = "shops"
    __repr_attrs__ = ("user_id", "name")

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )  # new - ondelete для целостности
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(512), nullable=False)
    address_link: Mapped[str] = mapped_column(String(512), nullable=False)
    phone_number: Mapped[list[str]] = mapped_column(ARRAY(String(30)), nullable=False)

    # Связи
    user: Mapped[User] = relationship(back_populates="shop")
    orders: Mapped[list[Order]] = relationship(back_populates="shop")
    ratings_given: Mapped[list[CourierRating]] = relationship(back_populates="shop")
