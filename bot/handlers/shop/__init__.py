# __init__.py — Сборщик роутеров магазина
from aiogram import Router

from .handlers import router as main_router
from .handlers_orders import router as orders_router

# Создаем главный роутер магазина
router = Router(name="shop")

# Подключаем все дочерние роутеры
router.include_router(main_router)
router.include_router(orders_router)

__all__ = ["router"]
