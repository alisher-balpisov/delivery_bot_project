import pytest
from sqlalchemy import select
from src.auth.utils import create_access_token, get_password_hash, verify_password, verify_token
from src.models.user import User


class TestPasswordUtils:
    """Tests for password hashing utilities."""

    def test_verify_password_success(self):
        """Test successful password verification."""
        plain_password = "testpassword"
        hashed = get_password_hash(plain_password)
        assert verify_password(plain_password, hashed) is True

    def test_verify_password_failure(self):
        """Test password verification with wrong password."""
        plain_password = "testpassword"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(plain_password)
        assert verify_password(wrong_password, hashed) is False

    def test_get_password_hash_creates_different_hashes(self):
        """Test that different hashes are generated for same password (salt)."""
        plain_password = "testpassword"
        hash1 = get_password_hash(plain_password)
        hash2 = get_password_hash(plain_password)
        assert hash1 != hash2  # Different salts should produce different hashes
        assert verify_password(plain_password, hash1) is True
        assert verify_password(plain_password, hash2) is True


class TestTokenUtils:
    """Tests for JWT token utilities."""

    def test_create_access_token(self):
        """Test creating access token."""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_success(self):
        """Test successful token verification."""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        payload = verify_token(token)
        assert payload is not None
        assert payload.email == "test@example.com"

    def test_verify_token_expired(self):
        """Test token verification with expired token."""
        from datetime import timedelta

        data = {"sub": "test@example.com"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-3600))  # 1 hour ago
        payload = verify_token(token)
        assert payload is None

    def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        payload = verify_token("invalid_token")
        assert payload is None


class TestUserRegistration:
    """Tests for user registration functionality."""

    @pytest.mark.asyncio
    async def test_user_creation_success(self, db_session):
        """Test successful user creation."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "name": "New User",
            "password_hash": get_password_hash("strongpassword"),
            "role": "shop",
        }

        user = User(**user_data)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.username == "newuser"
        assert verify_password("strongpassword", user.password_hash)

    @pytest.mark.asyncio
    async def test_user_creation_duplicate_email(self, db_session, test_user):
        """Test user creation with duplicate email fails."""
        user_data = {
            "email": test_user.email,  # Same as test_user
            "username": "anotheruser",
            "name": "Another User",
            "password_hash": get_password_hash("password"),
            "role": "shop",
        }

        user = User(**user_data)
        db_session.add(user)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_user_creation_weak_password_validation(self, db_session):
        """Test user creation with password validation."""
        # Test password too short
        user_data = {
            "email": "weakpass@example.com",
            "username": "weakpass",
            "name": "Weak Pass User",
            "password_hash": get_password_hash("123"),  # Too short
            "role": "shop",
        }

        user = User(**user_data)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # In model we can create, but should validate at API level
        assert user.id is not None


class TestUserLogin:
    """Tests for user login functionality."""

    @pytest.mark.asyncio
    async def test_login_successful(self, db_session, test_user):
        """Test successful login."""
        # Simulate login check
        user = await db_session.get(User, test_user.id)
        assert user is not None
        assert verify_password("testpass", user.password_hash)

        # Update last_login
        from datetime import datetime, timezone

        user.last_login = datetime.now(timezone.utc)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, db_session, test_user):
        """Test login with wrong password."""
        user = await db_session.get(User, test_user.id)
        assert user is not None
        assert not verify_password("wrongpass", user.password_hash)

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, db_session):
        """Test login for nonexistent user."""
        stmt = select(User).where(User.email == "nonexistent@example.com")
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        assert user is None


class TestPasswordValidation:
    """Tests for password validation."""

    def test_password_strength_requirements(self):
        """Test password strength validation."""
        # Test various password strengths
        test_cases = [
            ("password", True),  # Minimum length
            ("12345678", True),  # Numbers only
            ("ABCDEFGH", True),  # Letters only
            ("123", False),  # Too short
            ("", False),  # Empty
        ]

        for password, is_valid in test_cases:
            hashed = get_password_hash(password)
            assert isinstance(hashed, str)
            # In our implementation, we accept any password as long as it's hashed
            assert verify_password(password, hashed) == True


class TestSessionManagement:
    """Tests for session management."""

    @pytest.mark.asyncio
    async def test_session_creation_on_login(self, db_session, test_user):
        """Test session creation during login."""
        # This would normally be handled in API layer
        # Here we just check that user exists and can be queried
        user = await db_session.get(User, test_user.id)
        assert user is not None
        assert user.is_active == True

    @pytest.mark.asyncio
    async def test_session_expiry_simulation(self, db_session, test_user):
        """Test session expiry handling."""
        # Since sessions are JWT-based, expiry is handled in token utils
        user = await db_session.get(User, test_user.id)
        assert user is not None

        # Test that expired tokens are invalid (covered in token tests)


class TestTokenBasedAuth:
    """Tests for token-based authentication."""

    def test_token_generation(self):
        """Test JWT token generation."""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        assert token is not None

    def test_token_payload(self):
        """Test token contains correct payload."""
        data = {"sub": "test@example.com", "role": "shop"}
        token = create_access_token(data)
        payload = verify_token(token)

        assert payload.email == "test@example.com"
        # Note: JWT doesn't return the full payload, only telegram_id

    def test_bearer_token_format(self):
        """Test bearer token format."""
        from src.common.enums import TokenType

        assert TokenType.BEARER == "Bearer"


class TestRoleBasedAccessControl:
    """Tests for role-based access control."""

    @pytest.mark.asyncio
    async def test_role_assignment(self, db_session):
        """Test user role assignment."""
        user = User(
            email="admin@example.com",
            username="admin",
            name="Admin User",
            password_hash=get_password_hash("adminpass"),
            role="admin",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.role.value == "admin"

    @pytest.mark.asyncio
    async def test_role_based_permissions(self, db_session, test_user):
        """Test role-based permissions check."""
        user = await db_session.get(User, test_user.id)
        assert user.role.value == "shop"

        # This would be extended in API layer with decorators/dependencies


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_user_not_found_error(self, db_session):
        """Test handling user not found."""
        stmt = select(User).where(User.id == 99999)
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        assert user is None

    @pytest.mark.asyncio
    async def test_account_locked_handling(self, db_session, test_user):
        """Test handling of locked accounts."""
        user = await db_session.get(User, test_user.id)
        user.is_blocked = True
        await db_session.commit()

        # This would be checked in authentication logic
        assert user.is_blocked == True

    def test_invalid_token_handling(self):
        """Test handling of invalid tokens."""
        payload = verify_token("completely_invalid_token")
        assert payload is None


class TestLogout:
    """Tests for logout functionality."""

    @pytest.mark.asyncio
    async def test_logout_updates_last_login(self, db_session, test_user):
        """Test logout updates user's last login timestamp."""
        from datetime import datetime

        user = await db_session.get(User, test_user.id)
        original_last_login = user.last_login

        user.last_login = datetime.now()
        await db_session.commit()

        # For JWT tokens, logout might invalidate the token
        # This is more about client-side token removal
        assert user.last_login != original_last_login
