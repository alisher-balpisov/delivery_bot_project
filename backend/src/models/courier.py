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


class Courier(Base):
    """
    Модель профиля курьера.

    Создается при регистрации пользователя с ролью "курьер".
    Содержит информацию о курьере и связь с его заказами.
    """

    __tablename__ = "couriers"
    __repr_attrs__ = ("full_name", "is_active")

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="ID пользователя, связанного с профилем курьера",
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="ФИО курьера")
    phone_number: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(30)), nullable=True, comment="Контактные номера телефонов курьера"
    )
    photo_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="ID фотографии курьера в Telegram"
    )
    is_active: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        index=True,
        comment="Активен ли курьер (может ли принимать заказы)",
    )

    # Связь обратно к пользователю
    user: Mapped[User] = relationship(back_populates="courier", uselist=False, lazy="selectin")
    # Связь с заказами, назначенными курьеру
    orders: Mapped[list[Order]] = relationship(back_populates="courier", lazy="noload")
    ratings_received: Mapped[list[CourierRating]] = relationship(
        back_populates="courier", lazy="noload"
    )

    __table_args__ = (
        CheckConstraint(
            "full_name IS NULL OR length(trim(full_name)) > 0",
            name="check_courier_full_name_not_empty",
        ),
        CheckConstraint(
            "phone_number IS NULL OR cardinality(phone_number) > 0",
            name="check_courier_phone_number_not_empty",
        ),
    )
