import asyncio
import os
import sys

# Добавляем текущую директорию в path, чтобы импорты из backend.src работали
sys.path.append(os.getcwd())

from backend.src.common.enums import UserRole, UserStatus
from backend.src.core.database import engine
from sqlalchemy import text


async def fix_enums():
    async with engine.connect() as conn:
        # Проверяем и фиксим userrole
        try:
            result = await conn.execute(
                text(
                    "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'userrole'"
                )
            )
            existing_roles = {row[0] for row in result.fetchall()}
            print(f"Existing UserRoles: {existing_roles}")

            for role in UserRole:
                if role.value not in existing_roles:
                    print(f"Adding {role.value} to userrole enum")
                    # PostgreSQL требует, чтобы ADD VALUE выполнялся ВНЕ транзакции
                    # В asyncpg/SQLAlchemy мы можем попробовать выполнить это через прямое соединение
                    await conn.execute(text("COMMIT"))  # Пытаемся завершить текущую транзакцию
                    await conn.execute(text(f"ALTER TYPE userrole ADD VALUE '{role.value}'"))
                    print(f"Successfully added {role.value}")
        except Exception as e:
            print(f"Error while checking/fixing userrole: {e}")

        # Проверяем и фиксим userstatus
        try:
            result = await conn.execute(
                text(
                    "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'userstatus'"
                )
            )
            existing_statuses = {row[0] for row in result.fetchall()}
            print(f"Existing UserStatuses: {existing_statuses}")

            for status in UserStatus:
                if status.value not in existing_statuses:
                    print(f"Adding {status.value} to userstatus enum")
                    await conn.execute(text("COMMIT"))
                    await conn.execute(text(f"ALTER TYPE userstatus ADD VALUE '{status.value}'"))
                    print(f"Successfully added {status.value}")
        except Exception as e:
            print(f"Error while checking/fixing userstatus: {e}")


if __name__ == "__main__":
    asyncio.run(fix_enums())
