from fastapi import APIRouter
from src.admin.views import router as admin_router
from src.disputes.views import router as disputes_router
from src.notifications.views import router as notifications_router
from src.orders.views import router as orders_router
from src.users.views import router as users_router

api_router = APIRouter()

# TODO: Раскомментировать по мере реализации view-слоя
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(orders_router, prefix="/orders", tags=["Orders"])
api_router.include_router(disputes_router, prefix="/disputes", tags=["Disputes"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
