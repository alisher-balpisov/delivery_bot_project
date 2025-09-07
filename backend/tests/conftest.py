import asyncio
import os
import uuid

import pytest
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.core.database import Base
from src.models.user import User

# In-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
# загружаем .env из корня проекта
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def test_session_factory(test_engine):
    """Create test session factory."""
    async_session = sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    yield async_session


@pytest.fixture(scope="function")
async def db_session(test_session_factory):
    """Create test database session."""
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def client(test_session_factory):
    from src.api.deps import get_db as deps_get_db

    """Create test client."""
    from httpx import ASGITransport, AsyncClient
    from src.core.database import get_db

    from ..src.main import app

    # Override database dependency to use test session
    async def override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[deps_get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Clean up overrides after test
    try:
        if deps_get_db in app.dependency_overrides:
            del app.dependency_overrides[deps_get_db]
    except KeyError:
        pass
    try:
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]
    except KeyError:
        pass


@pytest.fixture
async def test_user(db_session):
    """Create test user."""
    from sqlalchemy import select

    # Generate unique email to avoid conflicts
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    # Check if user already exists
    stmt = select(User).where(User.email == unique_email)
    result = await db_session.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        return existing_user

    user = User(
        email=unique_email,
        username=f"testuser_{uuid.uuid4().hex[:4]}",
        name="Test User",
        password_hash="$2b$12$WmalAiwLS8iZMHhF.iEvV.b2S6pfb7fLz3m0LxYI29PxIlidv/UuS",  # password: testpass
        role="shop",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_telegram_user(db_session):
    """Create test user with telegram_id."""
    from sqlalchemy import select

    # Generate unique telegram_id to avoid conflicts
    telegram_id = int(uuid.uuid4().hex[:8], 16) % 1000000000  # Ensure it fits in integer

    # Check if user already exists
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await db_session.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        return existing_user

    user = User(
        telegram_id=telegram_id,
        name="Test Telegram User",
        role="shop",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
