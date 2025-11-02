from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.courier import Courier
from backend.src.models.user import User


async def get_shift_status(current_user: User) -> Courier:
    """
    Получает статус смены текущего аутентифицированного курьера.
    """
    return current_user.courier


async def toggle_courier_shift(
    db: AsyncSession,
    current_user: User,
) -> Courier:
    """
    Переключает статус смены (is_active) для текущего курьера.
    """
    courier = current_user.courier
    if not courier:
        return None

    courier.is_active = not courier.is_active

    db.add(courier)
    await db.commit()
    await db.refresh(courier)

    return courier
