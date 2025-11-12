"""
Упрощенный менеджер JWT токенов с использованием только Redis.

Ключевые изменения:
- Убрана зависимость от FSM (используется только Redis)
- Упрощена логика работы с токенами
- Улучшена обработка ошибок
"""

from backend.src.core.logging import get_logger
from bot.clients.auth_client import AuthClient
from bot.redis_storage import UserCacheData, UserDataStorage

logger = get_logger(__name__)


class TokenManager:
    """
    Менеджер для управления JWT токенами через Redis.

    Функции:
    - Автоматическое обновление токенов
    - Кэширование в Redis
    - Безопасное получение токенов
    - Обработка истечения срока действия
    """

    def __init__(self, auth_client: AuthClient, storage: UserDataStorage):
        self.auth_client = auth_client
        self.storage = storage

    async def get_token(self, telegram_id: int, force_refresh: bool = False) -> str | None:
        """
        Получает валидный access токен для пользователя.

        Алгоритм:
        1. Проверяет наличие токена в Redis
        2. Если токен истек или скоро истечет - обновляет
        3. Если refresh токен истек - требует повторную авторизацию

        Args:
            telegram_id: Telegram ID пользователя
            force_refresh: Принудительно обновить токен

        Returns:
            Access токен или None если требуется авторизация
        """
        # Получаем данные пользователя из Redis
        user_data = await self.storage.get_user_data(telegram_id)

        # Если данных нет - пробуем получить через login
        if not user_data:
            logger.debug(f"Данные пользователя {telegram_id} отсутствуют, пробуем login")
            return await self._login_and_cache(telegram_id)

        # Если refresh токен истек - требуется повторная авторизация
        if not user_data.refresh_token_valid:
            logger.warning(f"Refresh токен истек для пользователя {telegram_id}")
            await self.storage.invalidate_tokens(telegram_id)
            return None

        # Если access токен валиден и не требует обновления
        if not force_refresh and user_data.has_valid_token and not user_data.needs_token_refresh:
            logger.debug(f"Используем кэшированный токен для {telegram_id}")
            await self.storage.update_activity(telegram_id)
            return user_data.access_token

        # Обновляем токен через refresh
        logger.info(f"Обновляем токен для пользователя {telegram_id}")
        return await self._refresh_and_cache(telegram_id, user_data)

    async def save_token_from_response(
        self, response: dict, telegram_id: int, user_data: UserCacheData | None = None
    ) -> bool:
        """
        Сохраняет токены из ответа API в Redis.

        Args:
            response: Ответ от /auth/by-code, /auth/login или /auth/refresh
            telegram_id: Telegram ID пользователя
            user_data: Существующие данные пользователя (опционально)

        Returns:
            True при успехе
        """
        try:
            # Извлекаем данные из ответа
            access_token = response.get("access_token")
            refresh_token = response.get("refresh_token")
            expires_in = response.get("expires_in")
            refresh_expires_in = response.get("refresh_expires_in")

            if not all([access_token, refresh_token, expires_in, refresh_expires_in]):
                logger.error(f"Неполные данные токена в ответе для {telegram_id}")
                return False

            # Если данных пользователя нет - создаем минимальные
            if not user_data:
                user_info = response.get("user", {})
                user_data = UserCacheData(
                    user_id=user_info.get("id"),
                    telegram_id=telegram_id,
                    name=user_info.get("name"),
                    role=user_info.get("role", "guest"),
                    username=user_info.get("username"),
                )

            # Сохраняем токены
            success = await self.storage.save_tokens(
                telegram_id=telegram_id,
                access_token=access_token,
                refresh_token=refresh_token,
                access_expires_in=expires_in,
                refresh_expires_in=refresh_expires_in,
            )

            if success:
                # Также обновляем данные пользователя
                await self.storage.save_user_data(telegram_id, user_data)
                logger.info(f"Токены сохранены для {telegram_id} (expires_in={expires_in}s)")

            return success

        except Exception as e:
            logger.error(f"Ошибка при сохранении токена для {telegram_id}: {e}", exc_info=True)
            return False

    async def invalidate_token(self, telegram_id: int) -> bool:
        """
        Инвалидирует токены пользователя (при logout).

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            True при успехе
        """
        success = await self.storage.invalidate_tokens(telegram_id)

        if success:
            logger.info(f"Токены инвалидированы для {telegram_id}")

        return success

    # === Приватные методы ===

    async def _login_and_cache(self, telegram_id: int) -> str | None:
        """
        Получает токен через /auth/login и кэширует его.

        Returns:
            Access токен или None при ошибке
        """
        try:
            result = await self.auth_client.login(telegram_id)

            if not result.success or not isinstance(result.data, dict):
                logger.debug(
                    f"Не удалось получить токен через login для {telegram_id}: "
                    f"{result.status_code} - {result.detail}"
                )
                return None

            # Получаем существующие данные пользователя (если есть)
            user_data = await self.storage.get_user_data(telegram_id)

            # Сохраняем токены
            await self.save_token_from_response(result.data, telegram_id, user_data)

            return result.data["access_token"]

        except Exception as e:
            logger.error(f"Ошибка при login для {telegram_id}: {e}", exc_info=True)
            return None

    async def _refresh_and_cache(self, telegram_id: int, user_data: UserCacheData) -> str | None:
        """
        Обновляет токен через /auth/refresh и кэширует.

        Returns:
            Новый access токен или None при ошибке
        """
        try:
            if not user_data.refresh_token:
                logger.error(f"Отсутствует refresh токен для {telegram_id}")
                return None

            result = await self.auth_client.refresh_token(user_data.refresh_token)

            if result.success and isinstance(result.data, dict):
                # Сохраняем новые токены
                await self.save_token_from_response(result.data, telegram_id, user_data)
                return result.data["access_token"]
            else:
                logger.error(
                    f"Не удалось обновить токен для {telegram_id}: "
                    f"{result.status_code} - {result.detail}"
                )
                # Инвалидируем токены при ошибке
                await self.storage.invalidate_tokens(telegram_id)
                return None

        except Exception as e:
            logger.error(f"Ошибка при обновлении токена для {telegram_id}: {e}", exc_info=True)
            # При критической ошибке возвращаем старый токен
            return user_data.access_token


__all__ = ["TokenManager"]
