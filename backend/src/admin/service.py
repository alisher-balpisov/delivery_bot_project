import secrets
import string

from sqlalchemy.ext.asyncio import AsyncSession
from src.common.enums import UserRole
from src.models.registration_code import RegistrationCode
from src.schemas.registration_code import RegistrationCodeResponse


async def generate_registration_code(
    db: AsyncSession, role: UserRole, created_by_admin_id: int | None = None
) -> RegistrationCodeResponse:
    """
    Генерирует одноразовый код регистрации для пользователя.

    Args:
        db: Сессия базы данных
        role: Роль для которой генерируется код (shop или courier)
        created_by_admin_id: ID админа, который создал код (опционально)

    Returns:
        RegistrationCodeResponse: Созданный код регистрации
    """
    # Генерируем уникальный код длиной 8 символов
    while True:
        code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

        # Проверяем уникальность
        existing = await db.execute(db.query(RegistrationCode).where(RegistrationCode.code == code))
        if not existing.scalars().first():
            break

    # Создаем запись кода
    reg_code = RegistrationCode(code=code, role=role, is_used=False)

    db.add(reg_code)
    await db.commit()
    await db.refresh(reg_code)

    return RegistrationCodeResponse.model_validate(reg_code)


async def get_all_registration_codes(db: AsyncSession) -> list[RegistrationCodeResponse]:
    """
    Получить все коды регистрации (для администраторов).
    """
    result = await db.execute(
        db.query(RegistrationCode).order_by(RegistrationCode.created_at.desc())
    )
    codes = result.scalars().all()
    return [RegistrationCodeResponse.model_validate(code) for code in codes]


async def deactivate_registration_code(db: AsyncSession, code_id: int) -> bool:
    """
    Деактивировать код регистрации (поместить в черный список).

    Returns:
        bool: True если код был найден и деактивирован
    """
    result = await db.execute(db.query(RegistrationCode).where(RegistrationCode.id == code_id))
    code = result.scalars().first()

    if not code:
        return False

    # Помечаем как использованный
    code.is_used = True
    await db.commit()

    return True


async def get_registration_codes_by_role(
    db: AsyncSession, role: UserRole
) -> list[RegistrationCodeResponse]:
    """
    Получить все коды регистрации для определенной роли.
    """
    result = await db.execute(
        db.query(RegistrationCode)
        .where(RegistrationCode.role == role)
        .order_by(RegistrationCode.created_at.desc())
    )
    codes = result.scalars().all()
    return [RegistrationCodeResponse.model_validate(code) for code in codes]


async def get_unused_registration_codes_count(db: AsyncSession) -> dict:
    """
    Получить количество неиспользованных кодов по ролям.
    """
    # Получаем количество неиспользованных кодов для каждой роли
    shop_count = await db.execute(
        db.query(RegistrationCode).where(
            RegistrationCode.role == UserRole.shop, RegistrationCode.is_used is False
        )
    )

    courier_count = await db.execute(
        db.query(RegistrationCode).where(
            RegistrationCode.role == UserRole.courier, RegistrationCode.is_used is False
        )
    )

    return {
        "shop": len(shop_count.scalars().all()),
        "courier": len(courier_count.scalars().all()),
        "total": len(shop_count.scalars().all()) + len(courier_count.scalars().all()),
    }
