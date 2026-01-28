# __init__.py — Сборщик роутеров магазина
from aiogram import Router

from .handlers import router as main_router
from .handlers_create_orders import router as create_orders_router
from .handlers_current_orders import router as current_orders_router

# Создаем главный роутер магазина
router = Router(name="shop")

# Подключаем все дочерние роутеры
router.include_router(main_router)
router.include_router(create_orders_router)
router.include_router(current_orders_router)

__all__ = ["router"]
