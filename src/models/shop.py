from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.database import Base


class Shop(Base):
    """
    Представляет профиль магазина в таблице `shops`.

    Магазин связан с конкретным пользователем и является создателем заказов.
    """

    __tablename__ = "shops"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    address = Column(String(255))

    user = relationship("User", back_populates="shop")
    orders = relationship("Order", back_populates="shop", cascade="all, delete-orphan")
    disputes = relationship("Dispute", back_populates="shop")

    def __repr__(self):
        return f"<Shop(id={self.id}, name='{self.name}')>"
