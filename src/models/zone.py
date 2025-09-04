from sqlalchemy import DECIMAL, Column, Integer, String
from sqlalchemy.orm import relationship
from src.core.database import Base


class Zone(Base):
    """
    Представляет зону доставки в таблице `zones`.

    Определяет географическую зону с радиусом, базовой ценой и надбавками.
    """

    __tablename__ = "zones"
    __repr_attrs__ = ("name", "radius_km")

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)  # Название зоны (центр города и т.д.)
    radius_km = Column(Integer, nullable=False)  # Радиус зоны в километрах
    base_price = Column(
        DECIMAL(10, 2), nullable=False, default=3000.00
    )  # Фиксированная цена для обычных заказов
    # TODO: добавить координаты центра зоны для гео расчетов

    orders = relationship("Order", back_populates="zone")

    def __repr__(self):
        return f"<Zone(id={self.id}, name={self.name}, radius={self.radius_km}km, base_price={self.base_price})>"
