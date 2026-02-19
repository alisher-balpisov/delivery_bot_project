from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import ChangeType
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class OrderHistory(Base):
    """
    Модель истории изменений заказа.

    Записывает все изменения статусов и параметров заказа
    для аудита и отслеживания жизненного цикла заказа.
    """

    __tablename__ = "order_history"
    __repr_attrs__ = ("order_id", "change_type")

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True, comment="ID заказа"
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="ID пользователя, внесшего изменение",
    )
    change_type: Mapped[ChangeType] = mapped_column(
        ENUM(
            ChangeType,
            name="changetype",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    changes: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="JSON с деталями изменений"
    )

    # Связи
    order: Mapped[Order] = relationship(back_populates="history", lazy="noload")
    changed_by_user: Mapped[User | None] = relationship(
        back_populates="order_history_entries", lazy="noload"
    )

    __table_args__ = (Index("ix_order_history_order_created", "order_id", "created_at"),)
