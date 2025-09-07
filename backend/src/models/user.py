from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
from src.common.enums import UserRole
from src.core.database import Base


class User(Base):
    """
    Представляет пользователя системы в таблице `users`.

    Это центральная модель для идентификации, хранящая основные данные,
    такие как Telegram ID, и определяющая роль пользователя (магазин, курьер, админ).
    """

    __tablename__ = "users"
    __repr_attrs__ = ("name", "email", "role.name")

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=True, index=True)  # Теперь nullable для традиционной аутентификации
    email = Column(String(100), unique=True, nullable=True, index=True)  # Для традиционной аутентификации
    username = Column(String(50), unique=True, nullable=True)  # Альтернативный способ входа
    password_hash = Column(String(255), nullable=True)  # Хэш пароля для традиционной аутентификации
    name = Column(String(100))
    phone = Column(String(20), unique=True, nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    registration_code_id = Column(Integer, ForeignKey("registration_codes.id"), nullable=True)
    registration_attempts = Column(Integer, default=0, nullable=False)  # Попытки ввода кода
    is_blocked = Column(
        Boolean, default=False, nullable=False
    )  # Заблокирован после 3 неудачных попыток
    is_active = Column(Boolean, default=True, nullable=False)  # Активен ли аккаунт
    last_login = Column(DateTime, nullable=True)  # Время последнего входа

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    shop = relationship("Shop", back_populates="user", uselist=False, cascade="all, delete-orphan")
    courier = relationship(
        "Courier", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    registration_code = relationship(
        "RegistrationCode", back_populates="user", uselist=False, cascade="all, delete-orphan", single_parent=True
    )
