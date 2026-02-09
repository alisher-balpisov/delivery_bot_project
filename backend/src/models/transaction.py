from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.common.enums import TransactionType
from backend.src.core.database import Base

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class Transaction(Base):
    """
    Журнал финансовых операций.
    Реализует принцип двойной записи: сумма всех транзакций в системе всегда = 0.
    """

    __tablename__ = "transactions"
    __repr_attrs__ = ("user_id", "amount", "type", "order_id")

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="Пользователь, чей баланс изменяется",
    )

    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"),
        nullable=True,
        index=True,
        comment="Привязка к заказу (для автоматических начислений)",
    )

    type: Mapped[TransactionType] = mapped_column(
        ENUM(
            TransactionType,
            name="transactiontype",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )

    # amount < 0: Пользователь становится должен системе (или уменьшается долг системы перед ним)
    # amount > 0: Система становится должна пользователю (или уменьшается долг пользователя)
    amount: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 0), nullable=False, comment="Сумма операции"
    )

    description: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Описание транзакции"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="Кто провел операцию"
    )

    # Связи
    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")
    order: Mapped[Order] = relationship(lazy="select")
    admin: Mapped[User | None] = relationship(foreign_keys=[created_by_admin_id], lazy="select")

    __table_args__ = (CheckConstraint("amount != 0", name="check_transaction_amount_not_zero"),)
