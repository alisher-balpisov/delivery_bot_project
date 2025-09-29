from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import UserRole
from backend.src.core.database import Base
from backend.src.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from .user import User


class RegistrationCode(CreatedAtMixin, Base):
    __tablename__ = "registration_codes"
    __repr_attrs__ = ("id", "code", "role", "is_used")

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    is_used: Mapped[bool] = mapped_column(default=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    created_by_user: Mapped[User] = relationship(
        foreign_keys=[created_by_user_id], back_populates="created_registration_codes"
    )
    user: Mapped[User | None] = relationship(back_populates="registration_code", uselist=False)
