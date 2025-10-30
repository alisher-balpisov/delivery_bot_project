from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.user import User


async def toggle_courier_shift(
    db: AsyncSession,
    current_user: User,
):
    courier = current_user.courier
    courier.is_active = not courier.is_active

    db.commit()
    db.refresh(courier)
    return courier
