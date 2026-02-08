from fastapi import APIRouter

from backend.src.admin.views import router as admin_router
from backend.src.auth.views import router as auth_router
from backend.src.couriers.views import router as couriers_router
from backend.src.disputes.views import router as disputes_router
from backend.src.orders.views import router as orders_router
from backend.src.shops.views import router as shops_router
from backend.src.stats.views import router as stat_router
from backend.src.users.views import router as users_router

# from backend.src.notifications.views import router as notifications_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(users_router, prefix="", tags=["Users"])
api_router.include_router(shops_router, prefix="/shops", tags=["Shops"])
api_router.include_router(couriers_router, prefix="/couriers", tags=["Couriers"])
api_router.include_router(orders_router, prefix="/orders", tags=["Orders"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
api_router.include_router(stat_router, prefix="/statistics", tags=["Statistics"])
api_router.include_router(disputes_router, prefix="/disputes", tags=["Disputes"])
# api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
