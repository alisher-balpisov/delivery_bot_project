# __init__.py — Главный сборщик всех хендлеров бота
from aiogram import Router

from .admin import router as admin_router
from .auth import router as auth_router
from .common import router as common_router
from .courier import router as courier_router
from .public import router as public_router
from .shop import router as shop_router

# Роутер для заказов (объединяет shop и courier)
# В новой структуре orders распределены внутри модулей shop и courier
orders_router = Router(name="orders")
orders_router.include_router(shop_router)
orders_router.include_router(courier_router)

# Роутер для защищенных областей
protected_router = Router(name="protected")
protected_router.include_router(common_router)
protected_router.include_router(admin_router)

__all__ = ["auth_router", "orders_router", "protected_router", "public_router"]
