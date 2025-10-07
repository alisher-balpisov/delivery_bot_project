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


class Courier(Base):
    __tablename__ = "couriers"
    __repr_attrs__ = ("user_id", "full_name", "is_active")

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )  # new
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[list[str]] = mapped_column(ARRAY(String(30)), nullable=False)
    photo_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=False)

    # Связь обратно к пользователю
    user: Mapped[User] = relationship(back_populates="courier")
    # Связь с заказами, назначенными курьеру
    orders: Mapped[list[Order]] = relationship(back_populates="courier")
    ratings_received: Mapped[list[CourierRating]] = relationship(back_populates="courier")
