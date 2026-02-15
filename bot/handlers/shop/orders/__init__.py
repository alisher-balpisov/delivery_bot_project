"""Модуль заказов магазина."""

from aiogram import Router

from .create import router as create_router
from .current import router as current_router
from .dispute import router as dispute_router

router = Router(name="shop_orders")

router.include_router(create_router)
router.include_router(current_router)
router.include_router(dispute_router)

__all__ = ["router"]
