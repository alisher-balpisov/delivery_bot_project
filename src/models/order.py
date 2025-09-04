from sqlalchemy import (
    DECIMAL,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from src.common.enums import OrderStatus, OrderType
from src.core.database import Base


class Order(Base):
    """
    Представляет заказ в таблице `orders`.

    Это центральная модель бизнес-логики, хранящая всю информацию о доставке,
    статусе, участниках и деталях заказа.
    """

    __tablename__ = "orders"
    __repr_attrs__ = ("status.name", "shop_id")
    __table_args__ = (
        CheckConstraint(
            "courier_rating IS NULL OR (courier_rating >= 1 AND courier_rating <= 5)",
            name="check_courier_rating_range",
        ),
    )

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    # Может быть NULL, если заказ еще не назначен курьеру.
    courier_id = Column(Integer, ForeignKey("couriers.id"), nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.created, nullable=False, index=True)
    order_type = Column(Enum(OrderType), default=OrderType.normal, nullable=False)
    description = Column(Text)
    recipient_name = Column(String(100))
    recipient_phone = Column(String(20), nullable=False)
    recipient_address = Column(String(255), nullable=False)
    delivery_time = Column(DateTime, nullable=True)  # Ожидаемое время доставки
    price = Column(
        DECIMAL(10, 2), nullable=False
    )  # Используется DECIMAL для точности финансовых расчетов

    pickup_address = Column(String(255), nullable=False)  # Адрес забора
    courier_notes = Column(Text, nullable=True)  # Заметки курьера
    completion_notes = Column(Text, nullable=True)  # Заметки о завершении

    # --- Поля для реализации логики из описания ---
    is_fragile = Column(Boolean, default=False)  # Отметка "Хрупкое"
    is_bulky = Column(Boolean, default=False)  # Отметка "Крупногабаритное"
    special_reason = Column(Text, nullable=True)  # Пояснения для особого заказа (размер, хрупкость)

    # --- Доплаты для разных типов заказов ---
    zone_addon = Column(DECIMAL(10, 2), default=0)  # Надбавка за зону (для long_distance, rush_hour)
    rush_hour_addon = Column(DECIMAL(10, 2), default=0)  # Надбавка за внерабочее время (1000-1500)

    courier_rating = Column(Integer, nullable=True)  # Оценка курьера от 1 до 5
    courier_feedback = Column(Text, nullable=True)  # Текстовый отзыв о работе курьера

    # --- Временные метки для отслеживания жизненного цикла заказа ---
    accepted_at = Column(DateTime, nullable=True)  # Время принятия заказа курьером
    delivered_at = Column(DateTime, nullable=True)  # Фактическое время доставки
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    shop = relationship("Shop", back_populates="orders")
    courier = relationship("Courier", back_populates="orders")
    dispute = relationship(
        "Dispute", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    photo_reports = relationship(
        "PhotoReport", back_populates="order", cascade="all, delete-orphan"
    )
