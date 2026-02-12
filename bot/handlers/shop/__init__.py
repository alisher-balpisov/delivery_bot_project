"""
Модуль обработчиков для магазинов.
Объединяет все роутеры в единую точку входа.
"""

from aiogram import Router

from .main import router as main_router
from .orders import router as orders_router

# Главный роутер магазина
router = Router(name="shop")

# Подключение модулей
router.include_router(main_router)
router.include_router(orders_router)

__all__ = ["router"]
