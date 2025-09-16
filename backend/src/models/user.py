from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from backend.src.common.enums import UserRole
from backend.src.core.database import Base


class User(Base):
    """
    Представляет пользователя системы.
    Аутентификация происходит исключительно по telegram_id.
    """

    __tablename__ = "users"
    __repr_attrs__ = ("name", "role")

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)

    # Эти поля заполняются после успешной регистрации
    name = Column(String(100), nullable=True)
    phone = Column(String(20), unique=True, nullable=True)

    # Используем native_enum=False для совместимости с существующими данными в БД
    role = Column(Enum(UserRole, native_enum=False), default=UserRole.PENDING, nullable=False)

    # Для логики блокировки при неверном вводе кода
    login_attempts = Column(Integer, default=0, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Связь с использованным кодом
    registration_code_id = Column(Integer, ForeignKey("registration_codes.id"), nullable=True)
    registration_code = relationship("RegistrationCode", foreign_keys=[registration_code_id])

    # Связи с другими моделями (Shop, Courier) остаются как были
    shop = relationship("Shop", back_populates="user", uselist=False, cascade="all, delete-orphan")
    courier = relationship(
        "Courier", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
