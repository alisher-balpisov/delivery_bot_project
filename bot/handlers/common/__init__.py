# __init__.py — Сборщик роутеров common
from aiogram import Router

from .handlers import router as main_router

# Создаем главный роутер common
router = Router(name="common")

# Подключаем все дочерние роутеры
router.include_router(main_router)

__all__ = ["router"]
