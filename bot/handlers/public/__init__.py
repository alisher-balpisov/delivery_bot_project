# __init__.py — Сборщик роутеров public
from aiogram import Router

from .handlers import router as main_router

# Создаем главный роутер public
router = Router(name="public")

# Подключаем все дочерние роутеры
router.include_router(main_router)

__all__ = ["router"]
