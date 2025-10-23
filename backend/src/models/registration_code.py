from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import UserRole
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .user import User


class RegistrationCode(Base):
    """
    Модель кода регистрации.

    Коды создаются администратором для регистрации новых пользователей
    с определенными ролями (магазин/курьер).
    """

    __tablename__ = "registration_codes"
    __repr_attrs__ = ("code", "role_type", "is_used")

    code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True, comment="Уникальный код регистрации"
    )
    role_type: Mapped[UserRole] = mapped_column(
        ENUM(UserRole, create_type=False),
        nullable=False,
        index=True,
        comment="Роль, которую получит пользователь при использовании кода",
    )
    is_used: Mapped[bool] = mapped_column(
        nullable=False, default=False, index=True, comment="Использован ли код"
    )
    used_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
        comment="ID пользователя, использовавшего код",
    )
    created_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID администратора, создавшего код",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Дата и время истечения срока действия кода",
    )

    # Связи
    used_by_user: Mapped[User | None] = relationship(foreign_keys=[used_by_user_id], lazy="joined")
    created_by_admin: Mapped[User] = relationship(foreign_keys=[created_by_admin_id], lazy="joined")

    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="check_reg_code_not_empty"),
        CheckConstraint(
            "is_used = (used_by_user_id IS NOT NULL)",
            name="check_reg_code_usage_logic",
        ),
    )
