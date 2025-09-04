from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import relationship
from src.common.enums import UserRole
from src.core.database import Base


class RegistrationCode(Base):
    """
    Представляет код для регистрации в таблице `registration_codes`.

    Одноразовый код, который админы отправляют для регистрации магазинов и курьеров.
    """

    __tablename__ = "registration_codes"
    __repr_attrs__ = ("code", "role.name", "is_used")

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False)  # shop или courier
    is_used = Column(Boolean, default=False, nullable=False)
    user_id = Column(Integer, nullable=True)  # Устанавливается после использования
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)  # Можно установить срок действия

    user = relationship(
        "User", back_populates="registration_code", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<RegistrationCode(code='{self.code}', role={self.role.value}, used={self.is_used})>"
        )
