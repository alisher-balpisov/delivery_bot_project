# __init__.py — Сборщик роутеров админа
import statistics

from aiogram import Router

from .handlers import router as main_router
from .handlers_codes import router as codes_router
from .handlers_couriers import router as couriers_router
from .handlers_disputes import router as disputes_router
from .handlers_orders import router as orders_router
from .handlers_shops import router as shops_router
from .handlers_statistics import router as statistics_router
from .handlers_stats import router as stats_router

# Создаем главный роутер админа
router = Router(name="admin")

# Подключаем все дочерние роутеры
router.include_router(main_router)
router.include_router(codes_router)
router.include_router(stats_router)
router.include_router(orders_router)
router.include_router(couriers_router)
router.include_router(shops_router)
router.include_router(disputes_router)
router.include_router(statistics_router)

__all__ = ["router"]
