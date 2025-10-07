from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import UserRole
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .user import User


class RegistrationCode(Base):
    __tablename__ = "registration_codes"
    __repr_attrs__ = ("code", "role_type", "is_used")

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    role_type: Mapped[UserRole] = mapped_column(
        ENUM(UserRole, create_type=False), nullable=False
    )  # new
    is_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    used_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )  # new
    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )  # new
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Связи
    created_by_admin: Mapped[User] = relationship(back_populates="created_codes")
