from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import UserRole, UserStatus
from backend.src.core.database import Base
from backend.src.models.order_history import OrderHistory

if TYPE_CHECKING:
    from .courier import Courier
    from .dispute import Dispute
    from .registration_code import RegistrationCode
    from .shop import Shop


class User(Base):
    __tablename__ = "users"
    __repr_attrs__ = ("telegram_id", "role", "status")

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )  # new - Добавлен индекс для быстрого поиска
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole | None] = mapped_column(
        ENUM(UserRole, create_type=False), nullable=True, index=True
    )  # new
    status: Mapped[UserStatus] = mapped_column(
        ENUM(UserStatus, create_type=False), nullable=False, default=UserStatus.pending_registration
    )  # new
    registration_attempts: Mapped[int] = mapped_column(nullable=False, default=0)

    # Связи один-к-одному с профилями
    shop: Mapped[Shop | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )  # new - Каскадное удаление профиля при удалении юзера
    courier: Mapped[Courier | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )  # new

    # Связи один-ко-многим
    order_history_entries: Mapped[list[OrderHistory]] = relationship(
        back_populates="changed_by_user"
    )
    opened_disputes: Mapped[list[Dispute]] = relationship(
        back_populates="opened_by_user", foreign_keys=[Dispute.opened_by_user_id]
    )
    fined_in_disputes: Mapped[list[Dispute]] = relationship(
        back_populates="fined_user", foreign_keys=[Dispute.fined_user_id]
    )
    created_codes: Mapped[list[RegistrationCode]] = relationship(back_populates="created_by_admin")
