from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from core.database import Base


class Courier(Base):
    """
    Представляет профиль курьера в таблице `couriers`.

    Содержит информацию о статусе курьера, его текущей и максимальной загрузке.
    """

    __tablename__ = "couriers"
    __repr_attrs__ = ("user_id", "is_active")

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    # Показывает, работает ли курьер в данный момент (на смене).
    is_active = Column(Boolean, default=False, nullable=False)
    # Счётчик текущих заказов в работе.
    current_orders = Column(Integer, default=0)
    # Максимальное количество заказов, которое курьер может взять одновременно.
    max_orders = Column(Integer, default=5, nullable=False)

    # Ограничения на уровне базы данных для обеспечения целостности данных.
    __table_args__ = (
        CheckConstraint("current_orders >= 0", name="check_current_orders_positive"),
        CheckConstraint("current_orders <= max_orders", name="check_max_orders_limit"),
    )

    user = relationship("User", back_populates="courier")
    orders = relationship("Order", back_populates="courier")
    disputes = relationship("Dispute", back_populates="courier")

    def __repr__(self):
        return f"<Courier(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"
