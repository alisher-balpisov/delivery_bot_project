import logging

from backend.src.models.registration_code import RegistrationCode
from backend.src.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def auth_by_code(db: AsyncSession, telegram_id: int, code: str):
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))

    if user:
        return {"already_registered": True}
    if user and user.is_blocked:
        return {"success": False, "blocked": True}

    registration_code = await db.scalar(
        select(RegistrationCode).where(
            RegistrationCode.code == code, RegistrationCode.is_used.is_(False)
        )
    )

    if registration_code:
        if not user:
            user = User(telegram_id=telegram_id)
            db.add(user)
            await db.flush()  # Получаем user.id до коммита

        user.role = registration_code.role
        user.login_attempts = 0
        user.is_blocked = False
        registration_code.is_used = True
        registration_code.user_id = user.id

        await db.commit()
        return {"success": True, "user": {"id": user.id, "role": user.role}}
    else:
        if not user:
            user = User(telegram_id=telegram_id)
            db.add(user)

        user.login_attempts += 1
        if user.login_attempts >= 5:  # Увеличим количество попыток до 5
            user.is_blocked = True
            await db.commit()
            return {"success": False, "blocked": True}
        else:
            await db.commit()
            return {"success": False, "attempts_left": 5 - user.login_attempts}
