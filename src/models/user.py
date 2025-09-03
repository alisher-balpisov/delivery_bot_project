from sqlalchemy import Column, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import relationship

from common.enums import UserRole
from core.database import Base


class User(Base):
    """
    Представляет пользователя системы в таблице `users`.

    Это центральная модель для идентификации, хранящая основные данные,
    такие как Telegram ID, и определяющая роль пользователя (магазин, курьер, админ).
    """

    __tablename__ = "users"
    __repr_attrs__ = ("name", "role.name")

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100))
    phone = Column(String(20), unique=True)
    role = Column(Enum(UserRole), nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    shop = relationship("Shop", back_populates="user", uselist=False, cascade="all, delete-orphan")
    courier = relationship(
        "Courier", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
