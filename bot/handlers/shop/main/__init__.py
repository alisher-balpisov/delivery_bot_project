"""Модуль главного меню и профиля магазина."""

from aiogram import Router

from .handlers import router as handlers_router
from .profile import router as profile_router

router = Router(name="shop_main")
router.include_router(handlers_router)
router.include_router(profile_router)

__all__ = ["router"]
