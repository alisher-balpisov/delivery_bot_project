from fastapi import APIRouter

# from backend.src.admin.views import router as admin_router
from backend.src.auth.views import router as auth_router

# from backend.src.disputes.views import router as disputes_router
# from backend.src.notifications.views import router as notifications_router
# from backend.src.orders.views import router as orders_router
from backend.src.users.views import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
# api_router.include_router(orders_router, prefix="/orders", tags=["Orders"])
# api_router.include_router(disputes_router, prefix="/disputes", tags=["Disputes"])
# api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
# api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
