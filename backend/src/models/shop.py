from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from src.core.database import Base


class Shop(Base):
    """
    Представляет профиль магазина в таблице `shops`.

    Магазин связан с конкретным пользователем и является создателем заказов.
    """

    __tablename__ = "shops"
    __repr_attrs__ = "name"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    address = Column(String(255))

    user = relationship("User", back_populates="shop")
    orders = relationship("Order", back_populates="shop", cascade="all, delete-orphan")
    disputes = relationship("Dispute", back_populates="shop")
