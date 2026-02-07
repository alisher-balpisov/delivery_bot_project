from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.common.constants import SYSTEM_TELEGRAM_ID
from backend.src.common.enums import UserRole, UserStatus
from backend.src.models import User


async def ensure_system_user(session: AsyncSession) -> User:
    """
    Создает или возвращает системного пользователя (Кошелек сервиса).
    """
    stmt = select(User).where(User.role == UserRole.SYSTEM)
    result = await session.execute(stmt)
    system_user = result.scalar_one_or_none()

    if not system_user:
        system_user = User(
            telegram_id=SYSTEM_TELEGRAM_ID,
            username="SystemWallet",
            role=UserRole.SYSTEM,
            status=UserStatus.ACTIVE,
            registration_attempts=0,
        )
        session.add(system_user)
        await session.commit()
        await session.refresh(system_user)
        print(f"✅ Created SYSTEM user with ID: {system_user.id}")

    return system_user
