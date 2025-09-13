from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from backend.src.common.enums import UserRole
from backend.src.core.database import Base


class RegistrationCode(Base):
    """
    Представляет одноразовый код для регистрации.
    """

    __tablename__ = "registration_codes"
    __repr_attrs__ = ("code", "role", "is_used")

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)

    # Используем native_enum=False для совместимости с существующими данными в БД
    role = Column(Enum(UserRole, native_enum=False), nullable=False)

    is_used = Column(Boolean, default=False, nullable=False)

    # ID пользователя, который активировал код
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="registration_code", foreign_keys=[user_id])

    created_at = Column(DateTime, server_default=func.now())
