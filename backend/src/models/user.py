from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import UserRole
from backend.src.core.database import Base
from backend.src.models.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from .courier import Courier
    from .registration_code import RegistrationCode
    from .shop import Shop


class User(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __repr_attrs__ = ("id", "telegram_id", "name", "role")

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.PENDING)
    is_blocked: Mapped[bool] = mapped_column(default=False)

    registration_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("registration_codes.id"), unique=True
    )

    shop: Mapped[Shop | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    courier: Mapped[Courier | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    registration_code: Mapped[RegistrationCode | None] = relationship(
        back_populates="user", foreign_keys=[registration_code_id]
    )
    created_registration_codes: Mapped[list[RegistrationCode]] = relationship(
        back_populates="created_by_user", foreign_keys="RegistrationCode.created_by_user_id"
    )

    __table_args__ = (
        Index("phone", postgresql_where=(phone is not None)),
        Index("idx_users_telegram_id", "telegram_id"),
        Index("idx_users_role", "role"),
        Index("idx_users_is_blocked", "is_blocked"),
    )
