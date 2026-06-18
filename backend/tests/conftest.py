# ruff: noqa: E402
import asyncio
import os
import uuid

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

os.environ.setdefault("TELEGRAM__BOT_TOKEN", "123456:test-token")
os.environ["DATABASE__URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT__SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN__SUPER_ADMIN_TELEGRAM_IDS", "1")

from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.auth.service import create_access_token
from backend.src.common.enums import UserRole, UserStatus
from backend.src.core.database import Base, get_db
from backend.src.main import app
from backend.src.models.user import User


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    test_url = make_url(TEST_DATABASE_URL)
    engine_kwargs = {}

    if test_url.drivername.startswith("sqlite"):
        engine_kwargs = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    elif "test" not in (test_url.database or "").lower():
        raise RuntimeError("TEST_DATABASE_URL must point to a test database.")

    engine = create_async_engine(TEST_DATABASE_URL, **engine_kwargs)
    async with engine.begin() as conn:
        import backend.src.models  # noqa: F401

        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
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
    """Create a non-authenticated test client."""

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    del app.dependency_overrides[get_db]


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Creates a test user with a random telegram_id and saves it to the DB."""
    user = User(
        telegram_id=int(uuid.uuid4().int & (1 << 31) - 1),
        username="test_user",
        role=UserRole.SHOP,
        status=UserStatus.ACTIVE,
        registration_attempts=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def authenticated_client(client: AsyncClient, test_user: User) -> AsyncClient:
    """
    Creates a test client that is pre-authenticated as the test_user.
    """
    # Create a JWT token for the test user
    token = create_access_token(test_user)
    # Set the Authorization header for all subsequent requests with this client
    client.headers = {"Authorization": f"Bearer {token}"}
    return client
