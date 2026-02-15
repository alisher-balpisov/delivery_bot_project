"""Модуль споров (магазин)."""

# Импортируем хендлеры, чтобы они зарегистрировались в роутере
from . import creation, view
from .router import router

__all__ = ["router"]
