import asyncio
import os
import uuid

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.auth.service import create_access_token
from backend.src.common.enums import UserRole
from backend.src.core.database import Base, get_db
from backend.src.main import app
from backend.src.models.user import User

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
        name="Test User",
        role=UserRole.SHOP,
        is_active=True,
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
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "role": test_user.role.value,
            "tid": str(test_user.telegram_id),
        }
    )
    # Set the Authorization header for all subsequent requests with this client
    client.headers = {"Authorization": f"Bearer {token}"}
    return client
