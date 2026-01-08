# __init__.py — Сборщик роутеров авторизации
from aiogram import Router

from .handlers import router as main_router
from .handlers_shop_reg import router as shop_reg_router

# Создаем главный роутер авторизации
router = Router(name="auth")

# Подключаем все дочерние роутеры
router.include_router(main_router)
router.include_router(shop_reg_router)

__all__ = ["router"]
