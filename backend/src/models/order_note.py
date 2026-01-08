from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import UserRole
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class OrderNote(Base):
    """
    Модель заметки к заказу.

    Используется для коммуникации между магазином и курьером.
    Каждая заметка привязана к конкретному заказу и автору.
    """

    __tablename__ = "order_notes"
    __repr_attrs__ = ("order_id", "author_role")

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID заказа, к которому относится заметка",
    )
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        comment="ID пользователя, написавшего заметку",
    )
    author_role: Mapped[UserRole] = mapped_column(
        ENUM(
            UserRole,
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        comment="Роль автора заметки (shop/courier)",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Текст заметки",
    )

    # Связи
    order: Mapped[Order] = relationship(back_populates="notes", lazy="select")
    author: Mapped[User] = relationship(lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "length(trim(content)) > 0",
            name="check_order_note_content_not_empty",
        ),
        Index("ix_order_notes_order_created", "order_id", "created_at"),
    )
