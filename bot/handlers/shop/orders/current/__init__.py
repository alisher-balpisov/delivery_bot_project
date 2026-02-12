"""Модуль текущих заказов."""

from aiogram import Router

from .actions import router as actions_router
from .details import router as details_router
from .list import router as list_router

router = Router(name="shop_current_orders")

router.include_router(list_router)
router.include_router(details_router)
router.include_router(actions_router)

__all__ = ["router"]
