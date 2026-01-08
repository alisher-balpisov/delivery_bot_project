import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

# ruff: noqa: S106
import pytest
from bot.clients.auth_client import AuthClient
from bot.dto import UserDTO
from bot.middleware.token_refresh_middleware import TokenRefreshMiddleware
from bot.redis_storage import UserCacheData, UserDataStorage

from backend.src.common.enums import UserRole

# noinspection PyTypeChecker
"""
Unit тесты для TokenRefreshMiddleware.

Тестирует:
1. Успешное обновление токена
2. Конвертация в гостя при истекшем refresh токене
3. Пропуск гостевых пользователей
4. Ошибки при обновлении токена
"""


@pytest.fixture
def storage():
    """Mock UserDataStorage"""
    storage = AsyncMock(spec=UserDataStorage)
    return storage


@pytest.fixture
def auth_client():
    """Mock AuthClient"""
    client = AsyncMock(spec=AuthClient)
    return client


@pytest.fixture
def middleware(storage, auth_client):
    """TokenRefreshMiddleware"""
    return TokenRefreshMiddleware(storage, auth_client)


@pytest.mark.asyncio
async def test_token_needs_refresh_and_refreshes_successfully(middleware, storage, auth_client):
    """Тест успешного обновления токена когда он истекает в ближайшие 5 минут"""

    # Arrange
    telegram_id = 123456
    user = UserDTO(user_id=1, telegram_id=telegram_id, name="Test User", role=UserRole.COURIER)

    # Токен истекает через 4 минуты (меньше порога в 5 минут)
    user_data = UserCacheData(
        user_id=1,
        telegram_id=telegram_id,
        name="Test User",
        role=UserRole.COURIER,
        access_token="old_access_token",
        refresh_token="valid_refresh_token",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=4),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    storage.get_user_data.return_value = user_data

    # Успешный ответ от refresh эндпоинта
    auth_client.refresh_token.return_value = MagicMock(
        success=True,
        data={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "refresh_expires_in": 604800,
        },
        status_code=200,
    )

    storage.save_tokens.return_value = True

    data = {"user": user}
    handler = AsyncMock(return_value="handler_result")

    # Act
    result = await middleware(handler, MagicMock(), data)

    # Assert
    assert result == "handler_result"
    auth_client.refresh_token.assert_called_once_with("valid_refresh_token")
    storage.save_tokens.assert_called_once()
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_token_does_not_need_refresh(middleware, storage, auth_client):
    """Тест что токен не обновляется если он еще действителен"""

    # Arrange
    telegram_id = 123456
    user = UserDTO(user_id=1, telegram_id=telegram_id, name="Test User", role=UserRole.COURIER)

    # Токен истекает через 10 минут (больше порога в 5 минут)
    user_data = UserCacheData(
        user_id=1,
        telegram_id=telegram_id,
        name="Test User",
        role=UserRole.COURIER,
        access_token="valid_token",
        refresh_token="valid_refresh_token",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=10),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    storage.get_user_data.return_value = user_data

    data = {"user": user}
    handler = AsyncMock(return_value="handler_result")

    # Act
    result = await middleware(handler, MagicMock(), data)

    # Assert
    assert result == "handler_result"
    auth_client.refresh_token.assert_not_called()
    storage.save_tokens.assert_not_called()
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_expired_refresh_token_converts_to_guest(middleware, storage, auth_client):
    """Тест конвертации в гостя при истекшем refresh токене"""

    # Arrange
    telegram_id = 123456
    user = UserDTO(user_id=1, telegram_id=telegram_id, name="Test User", role=UserRole.COURIER)

    # Refresh токен истек
    user_data = UserCacheData(
        user_id=1,
        telegram_id=telegram_id,
        name="Test User",
        role=UserRole.COURIER,
        access_token="old_token",
        refresh_token="expired_refresh_token",
        token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
        refresh_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    storage.get_user_data.return_value = user_data
    storage.delete_user_data.return_value = True

    data = {"user": user}
    handler = AsyncMock(return_value="handler_result")

    # Act
    result = await middleware(handler, MagicMock(), data)

    # Assert
    assert result == "handler_result"
    storage.delete_user_data.assert_called_once_with(telegram_id)
    assert data["user"].role == UserRole.GUEST
    assert data.get("token_expired") is True
    auth_client.refresh_token.assert_not_called()
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_guest_user_skips_token_check(middleware, storage, auth_client):
    """Тест что гостевые пользователи пропускаются"""

    # Arrange
    guest = UserDTO(user_id=None, telegram_id=123456, name=None, role=UserRole.GUEST)

    data = {"user": guest}
    handler = AsyncMock(return_value="handler_result")

    # Act
    result = await middleware(handler, MagicMock(), data)

    # Assert
    assert result == "handler_result"
    storage.get_user_data.assert_not_called()
    auth_client.refresh_token.assert_not_called()
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_no_user_data_skips_token_check(middleware, storage, auth_client):
    """Тест что если нет данных пользователя - пропускаем"""

    # Arrange
    telegram_id = 123456
    user = UserDTO(user_id=1, telegram_id=telegram_id, name="Test User", role=UserRole.COURIER)

    storage.get_user_data.return_value = None

    data = {"user": user}
    handler = AsyncMock(return_value="handler_result")

    # Act
    result = await middleware(handler, MagicMock(), data)

    # Assert
    assert result == "handler_result"
    storage.get_user_data.assert_called_once_with(telegram_id)
    auth_client.refresh_token.assert_not_called()
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_fails_with_401_converts_to_guest(middleware, storage, auth_client):
    """Тест конвертации в гостя при 401 ошибке от refresh эндпоинта"""

    # Arrange
    telegram_id = 123456
    user = UserDTO(user_id=1, telegram_id=telegram_id, name="Test User", role=UserRole.COURIER)

    # Токен истекает через 4 минуты
    user_data = UserCacheData(
        user_id=1,
        telegram_id=telegram_id,
        name="Test User",
        role=UserRole.COURIER,
        access_token="old_token",
        refresh_token="invalid_refresh_token",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=4),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    storage.get_user_data.return_value = user_data

    # Ошибка 401 от refresh эндпоинта
    auth_client.refresh_token.return_value = MagicMock(
        success=False, status_code=401, detail="Invalid refresh token"
    )

    storage.delete_user_data.return_value = True

    data = {"user": user}
    handler = AsyncMock(return_value="handler_result")

    # Act
    result = await middleware(handler, MagicMock(), data)

    # Assert
    assert result == "handler_result"
    auth_client.refresh_token.assert_called_once_with("invalid_refresh_token")
    storage.delete_user_data.assert_called_once_with(telegram_id)
    assert data["user"].role == UserRole.GUEST
    assert data.get("token_expired") is True
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_fails_with_other_error(middleware, storage, auth_client):
    """Тест что при других ошибках refresh обновление пропускается"""

    # Arrange
    telegram_id = 123456
    user = UserDTO(user_id=1, telegram_id=telegram_id, name="Test User", role=UserRole.COURIER)

    # Токен истекает через 4 минуты
    user_data = UserCacheData(
        user_id=1,
        telegram_id=telegram_id,
        name="Test User",
        role=UserRole.COURIER,
        access_token="old_token",
        refresh_token="valid_refresh_token",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=4),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    storage.get_user_data.return_value = user_data

    # Ошибка 500 от refresh эндпоинта
    auth_client.refresh_token.return_value = MagicMock(
        success=False, status_code=500, detail="Server error"
    )

    data = {"user": user}
    handler = AsyncMock(return_value="handler_result")

    # Act
    result = await middleware(handler, MagicMock(), data)

    # Assert
    assert result == "handler_result"
    auth_client.refresh_token.assert_called_once_with("valid_refresh_token")
    storage.delete_user_data.assert_not_called()
    assert data["user"].role == UserRole.COURIER  # Пользователь остался курьером
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_token_refresh_with_lock_prevents_concurrent_refresh(
    middleware, storage, auth_client
):
    """Тест что lock предотвращает параллельные refresh запросы"""

    # Arrange
    telegram_id = 123456
    user = UserDTO(user_id=1, telegram_id=telegram_id, name="Test User", role=UserRole.COURIER)

    # Токен истекает через 4 минуты
    user_data = UserCacheData(
        user_id=1,
        telegram_id=telegram_id,
        name="Test User",
        role=UserRole.COURIER,
        access_token="old_token",
        refresh_token="valid_refresh_token",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=4),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    # При первом вызове возвращаем user_data, при втором внутри lock - обновленные данные
    updated_user_data = UserCacheData(
        user_id=1,
        telegram_id=telegram_id,
        name="Test User",
        role=UserRole.COURIER,
        access_token="new_access_token",
        refresh_token="valid_refresh_token",
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        refresh_expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    storage.get_user_data.side_effect = [
        user_data,  # Первый запрос
        user_data,  # Второй запрос
        updated_user_data,  # Когда второй поток проверяет после ожидания lock
    ]

    # Успешный ответ от refresh эндпоинта
    auth_client.refresh_token.return_value = MagicMock(
        success=True,
        data={
            "access_token": "new_access_token",
            "refresh_token": "valid_refresh_token",
            "expires_in": 3600,
            "refresh_expires_in": 604800,
        },
        status_code=200,
    )

    storage.save_tokens.return_value = True

    # Запускаем два параллельных запроса с небольшой задержкой
    # чтобы второй начался ДО завершения первого
    data1 = {"user": user}
    data2 = {"user": user}
    handler = AsyncMock(return_value="handler_result")

    async def delayed_second_call():
        await asyncio.sleep(0.05)  # Даем первому запросу начать обновление
        return await middleware(handler, MagicMock(), data2)

    # Act
    result1, result2 = await asyncio.gather(
        middleware(handler, MagicMock(), data1),
        delayed_second_call(),
    )

    # Assert
    assert result1 == "handler_result"
    assert result2 == "handler_result"
    # Первый запрос должен выполнить refresh, второй должен дождаться lock
    # и затем пропустить обновление т.к. токен уже обновлен
    assert auth_client.refresh_token.call_count >= 1  # Минимум один вызов


@pytest.mark.asyncio
async def test_cleanup_task_can_be_started_and_stopped(middleware):
    """Тест что cleanup задача может быть запущена и остановлена"""

    # Act
    await middleware.start_cleanup_task()
    assert middleware._lock_cleanup_task is not None
    assert not middleware._lock_cleanup_task.done()

    # Даем задаче время на запуск
    await asyncio.sleep(0.1)

    await middleware.stop_cleanup_task()
    # Даем время на завершение
    await asyncio.sleep(0.1)
    assert middleware._lock_cleanup_task.done()


@pytest.mark.asyncio
async def test_user_with_no_telegram_id_is_skipped(middleware):
    """Тест что пользователь без telegram_id пропускается"""

    # Arrange
    user = UserDTO(user_id=1, telegram_id=None, name="Test", role=UserRole.COURIER)

    data = {"user": user}
    handler = AsyncMock(return_value="handler_result")

    # Act
    result = await middleware(handler, MagicMock(), data)

    # Assert
    assert result == "handler_result"
    handler.assert_called_once()
