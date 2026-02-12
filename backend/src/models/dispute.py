from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, and_, or_
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import DisputeResolutionType, DisputeStatus
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class Dispute(Base):
    """
    Модель спора/претензии по заказу.

    Создается когда магазин или курьер открывает спор по заказу.
    Может привести к штрафу одной из сторон после разрешения администратором.
    """

    __tablename__ = "disputes"
    __repr_attrs__ = ("order_id", "status")

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        unique=True,
        nullable=False,
        index=True,
        comment="ID заказа, по которому открыт спор",
    )
    opened_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="ID пользователя, открывшего спор",
    )
    fined_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="ID пользователя, которому назначен штраф",
    )
    resolved_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="ID администратора, разрешившего спор",
    )

    description: Mapped[str] = mapped_column(Text, nullable=False, comment="Описание причины спора")
    status: Mapped[DisputeStatus] = mapped_column(
        ENUM(
            DisputeStatus,
            name="disputestatus",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DisputeStatus.PENDING_REVIEW,
    )
    resolution_type: Mapped[DisputeResolutionType | None] = mapped_column(
        ENUM(
            DisputeResolutionType,
            name="disputeresolutiontype",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    resolution_comment: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Комментарий администратора по разрешению спора"
    )
    fine_amount: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Сумма штрафа (если назначен)"
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Дата и время разрешения спора"
    )

    # Связи
    order: Mapped[Order] = relationship(back_populates="dispute", lazy="joined")
    opened_by_user: Mapped[User] = relationship(
        back_populates="opened_disputes", foreign_keys=[opened_by_user_id], lazy="joined"
    )
    fined_user: Mapped[User | None] = relationship(
        back_populates="fined_in_disputes", foreign_keys=[fined_user_id], lazy="joined"
    )
    resolved_by_admin: Mapped[User | None] = relationship(
        foreign_keys=[resolved_by_admin_id], lazy="joined"
    )

    __table_args__ = (
        CheckConstraint(
            "fine_amount IS NULL OR fine_amount >= 0", name="check_fine_amount_non_negative"
        ),
        CheckConstraint(
            "length(trim(description)) > 0", name="check_dispute_description_not_empty"
        ),
        CheckConstraint(
            or_(
                status != DisputeStatus.RESOLVED,
                and_(resolved_at.is_not(None), resolution_type.is_not(None)),
            ),
            name="check_resolution_details_if_resolved",
        ),
        CheckConstraint(
            or_(
                fine_amount.is_(None),
                and_(status == DisputeStatus.RESOLVED, fined_user_id.is_not(None)),
            ),
            name="check_fine_logic",
        ),
    )
