from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class PhotoReport(Base):
    """
    Представляет фотоотчет по заказу в таблице `photo_reports`.

    Хранит ссылку на файл (file_id из Telegram) и другую мета-информацию.
    """

    __tablename__ = "photo_reports"
    __repr_attrs__ = "order_id"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    # file_id, полученный от Telegram API.
    file_id = Column(String(255), nullable=False)
    # Локальный путь, если файл сохраняется на сервере.
    file_path = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    order = relationship("Order", back_populates="photo_reports")
