from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import create_access_token, get_password_hash, verify_password
from src.core.logging import get_logger
from src.models.user import User

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations."""

    @staticmethod
    async def register_user(
        db: AsyncSession,
        email: str,
        username: str,
        password: str,
        name: str | None = None,
        role: str = "SHOP",
    ) -> User:
        """
        Register a new user with email and password.
        """
        # Hash the password
        password_hash = get_password_hash(password)

        # Create user
        user = User(
            email=email, username=username, password_hash=password_hash, name=name, role=role
        )

        try:
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"New user registered: {email}")
            return user
        except IntegrityError as e:
            await db.rollback()
            if "email" in str(e).lower():
                raise ValueError("Email already registered")
            elif "username" in str(e).lower():
                raise ValueError("Username already taken")
            raise ValueError("Registration failed")

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
        """
        Authenticate user with email and password.
        Returns user if authentication successful, None otherwise.
        """
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        if not user.is_active:
            raise ValueError("Account is deactivated")

        if user.is_blocked:
            raise ValueError("Account is blocked")

        if not verify_password(password, user.password_hash):
            return None

        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()

        return user

    @staticmethod
    async def change_password(
        db: AsyncSession, user_id: int, old_password: str, new_password: str
    ) -> bool:
        """
        Change user's password after verifying old password.
        """
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return False

        if not verify_password(old_password, user.password_hash):
            return False

        user.password_hash = get_password_hash(new_password)
        await db.commit()

        return True

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
        """
        Get user by email.
        """
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def deactivate_user(db: AsyncSession, user_id: int) -> bool:
        """
        Deactivate user account.
        """
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.is_active = False
        await db.commit()

        return True

    @staticmethod
    async def activate_user(db: AsyncSession, user_id: int) -> bool:
        """
        Activate user account.
        """
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.is_active = True
        await db.commit()

        return True

    @staticmethod
    def generate_token(user: User) -> str:
        """
        Generate JWT token for user.
        """
        return create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )


# Convenience functions
async def register_user(
    db: AsyncSession,
    email: str,
    username: str,
    password: str,
    name: str | None = None,
    role: str = "SHOP",
) -> User:
    return await AuthService.register_user(db, email, username, password, name, role)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    return await AuthService.authenticate_user(db, email, password)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await AuthService.get_user_by_email(db, email)


async def change_password(
    db: AsyncSession, user_id: int, old_password: str, new_password: str
) -> bool:
    return await AuthService.change_password(db, user_id, old_password, new_password)


async def deactivate_user(db: AsyncSession, user_id: int) -> bool:
    return await AuthService.deactivate_user(db, user_id)


async def activate_user(db: AsyncSession, user_id: int) -> bool:
    return await AuthService.activate_user(db, user_id)
