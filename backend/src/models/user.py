from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, String, and_, or_
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import UserRole, UserStatus
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .courier import Courier
    from .dispute import Dispute
    from .order_history import OrderHistory
    from .shop import Shop


class User(Base):
    """
    Модель пользователя системы.

    Пользователь может иметь одну из ролей: магазин, курьер или администратор.
    Каждый пользователь связан с Telegram аккаунтом через telegram_id.
    """

    __tablename__ = "users"
    __repr_attrs__ = ("telegram_id", "role", "status")

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
        comment="Уникальный ID пользователя в Telegram",
    )
    username: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Username пользователя в Telegram"
    )
    role: Mapped[UserRole] = mapped_column(
        ENUM(UserRole, name="userrole", create_type=True),
        nullable=False,
        default=UserRole.GUEST,
        server_default="GUEST",
        index=True,
        comment="Роль пользователя в системе",
    )
    status: Mapped[UserStatus] = mapped_column(
        ENUM(UserStatus, name="userstatus", create_type=True),
        nullable=False,
        default=UserStatus.PENDING_REGISTRATION,
        index=True,
        comment="Текущий статус регистрации пользователя",
    )
    registration_attempts: Mapped[int] = mapped_column(
        nullable=False, default=0, comment="Количество попыток регистрации"
    )

    # Связи один-к-одному
    shop: Mapped[Shop | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="joined"
    )
    courier: Mapped[Courier | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="joined"
    )

    # Связи один-ко-многим
    order_history_entries: Mapped[list[OrderHistory]] = relationship(
        back_populates="changed_by_user", lazy="selectin"
    )
    opened_disputes: Mapped[list[Dispute]] = relationship(
        back_populates="opened_by_user", foreign_keys="[Dispute.opened_by_user_id]", lazy="selectin"
    )
    fined_in_disputes: Mapped[list[Dispute]] = relationship(
        back_populates="fined_user", foreign_keys="[Dispute.fined_user_id]", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint(
            "registration_attempts >= 0", name="check_registration_attempts_non_negative"
        ),
        CheckConstraint(
            "username IS NULL OR length(trim(username)) > 0", name="check_user_username_not_empty"
        ),
        CheckConstraint(
            or_(
                and_(role == UserRole.GUEST, status == UserStatus.PENDING_REGISTRATION),
                and_(role != UserRole.GUEST, status != UserStatus.PENDING_REGISTRATION),
            ),
            name="check_user_role_and_status_logic",
        ),
    )
