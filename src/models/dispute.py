from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from common.enums import DisputeStatus, UserRole
from core.database import Base


class Dispute(Base):
    """
    Представляет спор по заказу в таблице `disputes`.
    """

    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True)
    # Уникальность гарантирует, что по одному заказу может быть только один спор.
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    # courier_id и shop_id дублируют данные из заказа, но могут быть полезны
    courier_id = Column(Integer, ForeignKey("couriers.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    description = Column(Text, nullable=False)  # Описание проблемы от создателя спора
    status = Column(Enum(DisputeStatus), default=DisputeStatus.open, nullable=False, index=True)
    # Роль пользователя, который открыл спор (магазин или курьер).
    created_by_role = Column(Enum(UserRole), nullable=False)
    admin_notes = Column(Text, nullable=True)  # Внутренние заметки администратора
    resolution_notes = Column(Text, nullable=True)  # Итоговое решение по спору

    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)

    order = relationship("Order", back_populates="dispute")
    courier = relationship("Courier", back_populates="disputes")
    shop = relationship("Shop", back_populates="disputes")

    def __repr__(self):
        return f"<Dispute(id={self.id}, order_id={self.order_id}, status='{self.status.name}')>"
