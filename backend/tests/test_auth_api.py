import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from src.models.user import User


class TestTelegramLogin:
    """API tests for Telegram-based login functionality."""

    @pytest.mark.asyncio
    async def test_telegram_login_success(self, client: AsyncClient, test_telegram_user):
        """Test successful login with valid telegram_id."""
        response = await client.post(
            "/api/v1/users/login", json={"telegram_id": test_telegram_user.telegram_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "Bearer"

    @pytest.mark.asyncio
    async def test_telegram_login_user_not_found(self, client: AsyncClient):
        """Test login with non-existent telegram_id."""
        response = await client.post("/api/v1/users/login", json={"telegram_id": 999999999})
        assert response.status_code == 404
        data = response.json()
        assert "Пользователь не найден" in data["detail"]

    @pytest.mark.asyncio
    async def test_telegram_login_blocked_user(
        self, client: AsyncClient, db_session, test_telegram_user
    ):
        """Test login with blocked user."""
        # Block the user
        test_telegram_user.is_blocked = True
        await db_session.commit()

        response = await client.post(
            "/api/v1/users/login", json={"telegram_id": test_telegram_user.telegram_id}
        )
        assert response.status_code == 404  # Should not find user (simulating blocked state)
        data = response.json()
        assert "Пользователь не найден" in data["detail"]

    @pytest.mark.asyncio
    async def test_telegram_login_inactive_user(
        self, client: AsyncClient, db_session, test_telegram_user
    ):
        """Test login with inactive user."""
        # Deactivate the user
        test_telegram_user.is_active = False
        await db_session.commit()

        response = await client.post(
            "/api/v1/users/login", json={"telegram_id": test_telegram_user.telegram_id}
        )
        assert response.status_code == 404
        data = response.json()
        assert "Пользователь не найден" in data["detail"]

    @pytest.mark.asyncio
    async def test_telegram_login_empty_telegram_id(self, client: AsyncClient):
        """Test login with empty telegram_id."""
        response = await client.post("/api/v1/users/login", json={})
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_telegram_login_invalid_telegram_id_negative(self, client: AsyncClient):
        """Test login with negative telegram_id."""
        response = await client.post("/api/v1/users/login", json={"telegram_id": -123456})
        assert response.status_code == 404


class TestBotAuthAPI:
    """API tests for bot authentication."""

    @pytest.mark.asyncio
    async def test_bot_auth_success(self, client: AsyncClient):
        """Test successful bot authentication with valid API key."""
        response = await client.post("/api/v1/auth/bot/token", json={"api_key": "test_bot_key"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "Bearer"

    @pytest.mark.asyncio
    async def test_bot_auth_invalid_api_key(self, client: AsyncClient):
        """Test bot authentication with invalid API key."""
        response = await client.post("/api/v1/auth/bot/token", json={"api_key": "invalid_key"})
        assert response.status_code == 401
        data = response.json()
        assert "Неверный API ключ бота" in data["detail"]

    @pytest.mark.asyncio
    async def test_bot_auth_empty_api_key(self, client: AsyncClient):
        """Test bot authentication with empty API key."""
        response = await client.post("/api/v1/auth/bot/token", json={})
        assert response.status_code == 422  # Validation error


class TestUserRegistrationAPI:
    """API tests for user registration."""

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self, client: AsyncClient, test_telegram_user):
        """Test getting user profile successfully."""
        response = await client.get(f"/api/v1/users/{test_telegram_user.telegram_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["telegram_id"] == test_telegram_user.telegram_id
        assert data["name"] == test_telegram_user.name
        assert data["role"] == test_telegram_user.role.value

    @pytest.mark.asyncio
    async def test_get_user_profile_not_found(self, client: AsyncClient):
        """Test getting profile for non-existent user."""
        response = await client.get("/api/v1/users/999999999")
        assert response.status_code == 404
        data = response.json()
        assert "Пользователь не найден" in data["detail"]


class TestRBACIntegration:
    """Integration tests for role-based access control."""

    @pytest.mark.asyncio
    async def test_user_role_assignment_shop(self, client: AsyncClient, test_telegram_user):
        """Test that telegram user has correct role assignment."""
        response = await client.post(
            "/api/v1/users/login", json={"telegram_id": test_telegram_user.telegram_id}
        )
        assert response.status_code == 200

        # Note: Actual RBAC testing would require protected endpoints
        # This is a placeholder for when protected routes are implemented
        assert "access_token" in response.json()


class TestEdgeCases:
    """Tests for edge cases in authentication."""

    @pytest.mark.asyncio
    async def test_concurrent_telegram_logins(self, client: AsyncClient, test_telegram_user):
        """Test multiple concurrent logins with same telegram_id."""
        import asyncio

        async def login_request():
            return await client.post(
                "/api/v1/users/login", json={"telegram_id": test_telegram_user.telegram_id}
            )

        # Execute multiple concurrent requests
        tasks = [login_request() for _ in range(3)]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
            assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_telegram_login_large_telegram_id(self, client: AsyncClient):
        """Test login with very large telegram_id."""
        large_id = 999999999999999  # 15 digits
        response = await client.post("/api/v1/users/login", json={"telegram_id": large_id})
        assert response.status_code == 404  # Should handle gracefully

    @pytest.mark.asyncio
    async def test_bot_auth_rate_limiting_simulation(self, client: AsyncClient):
        """Test bot auth handles multiple invalid attempts."""
        for _ in range(5):
            response = await client.post("/api/v1/auth/bot/token", json={"api_key": "wrong_key"})
            assert response.status_code == 401

        # Should still work with correct key
        response = await client.post("/api/v1/auth/bot/token", json={"api_key": "test_bot_key"})
        assert response.status_code == 200


class TestMultiRoleAuth:
    """Tests for authentication with different user roles."""

    @pytest.mark.asyncio
    async def test_create_user_with_different_roles(self, db_session):
        """Test user creation with different roles."""
        from src.common.enums import UserRole

        for role in [UserRole.shop, UserRole.courier, UserRole.admin]:
            telegram_id = int(uuid.uuid4().hex[:8], 16) % 1000000000
            user = User(
                telegram_id=telegram_id,
                name=f"Test User {role.value}",
                role=role,
                is_active=True,
            )
            db_session.add(user)

        await db_session.commit()

        # Verify users were created
        stmt = select(User).where(User.telegram_id.isnot(None))
        result = await db_session.execute(stmt)
        users = result.scalars().all()
        assert len(users) >= 3

        roles = {user.role for user in users}
        assert UserRole.shop in roles
        assert UserRole.courier in roles
        assert UserRole.admin in roles
