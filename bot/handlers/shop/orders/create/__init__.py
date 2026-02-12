"""Модуль создания заказов."""

from aiogram import Router

from .confirm import router as confirm_router
from .courier import router as courier_router
from .description import router as description_router
from .edit import router as edit_router
from .price import router as price_router
from .settings import router as settings_router

router = Router(name="order_create")

# Порядок важен - от специфичных к общим
router.include_router(description_router)
router.include_router(settings_router)
router.include_router(price_router)
router.include_router(courier_router)
router.include_router(edit_router)
router.include_router(confirm_router)

__all__ = ["router"]
