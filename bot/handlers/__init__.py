from aiogram import Router

from .admin.views import admin_router
from .auth.views import auth_router
from .common.views import common_router
from .courier.views import courier_router
from .public.views import public_router
from .shop.views import shop_router

orders_router = Router(name="orders")
orders_router.include_router(shop_router)
orders_router.include_router(courier_router)

protected_router = Router(name="protected")
protected_router.include_router(common_router)
protected_router.include_router(admin_router)


__all__ = ["auth_router", "orders_router", "protected_router", "public_router"]
