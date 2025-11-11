"""
Менеджер JWT токенов с автоматическим обновлением и кэшированием.

Этот модуль предоставляет централизованное управление токенами:
- Автоматическое обновление при истечении
- Кэширование в FSM
- Обработка ошибок
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram.fsm.context import FSMContext
from backend.src.core.logging import get_logger

from bot.clients.auth_client import AuthClient

logger = get_logger(__name__)


@dataclass
class TokenData:
    """Данные о токене с метаинформацией"""

    access_token: str
    refresh_token: str
    expires_at: datetime
    refresh_expires_at: datetime
    user_id: int

    @property
    def is_expired(self) -> bool:
        """Проверяет, истек ли access токен"""
        return datetime.utcnow() >= self.expires_at

    @property
    def needs_refresh(self) -> bool:
        """Проверяет, нужно ли обновить токен (за 5 минут до истечения)"""
        return datetime.utcnow() >= self.expires_at - timedelta(minutes=5)

    @property
    def refresh_expired(self) -> bool:
        """Проверяет, истек ли refresh токен"""
        return datetime.utcnow() >= self.refresh_expires_at

    def to_dict(self) -> dict:
        """Сериализует данные для хранения в FSM"""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
            "refresh_expires_at": self.refresh_expires_at.isoformat(),
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenData":
        """Десериализует данные из FSM"""
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            refresh_expires_at=datetime.fromisoformat(data["refresh_expires_at"]),
            user_id=data["user_id"],
        )

    @classmethod
    def from_api_response(cls, response: dict, user_id: int) -> "TokenData":
        """Создает TokenData из ответа API"""
        now = datetime.utcnow()

        return cls(
            access_token=response["access_token"],
            refresh_token=response["refresh_token"],
            expires_at=now + timedelta(seconds=response["expires_in"]),
            refresh_expires_at=now + timedelta(seconds=response["refresh_expires_in"]),
            user_id=user_id,
        )


class TokenManager:
    """
    Менеджер для управления JWT токенами.

    Функции:
    - Автоматическое обновление токенов
    - Кэширование в FSM
    - Безопасное получение токенов
    - Обработка истечения срока действия
    """

    FSM_KEY = "token_data"

    def __init__(self, auth_client: AuthClient):
        self.auth_client = auth_client

    async def get_token(
        self, state: FSMContext, telegram_id: int, force_refresh: bool = False
    ) -> str | None:
        """
        Получает валидный access токен.

        Алгоритм:
        1. Проверяет наличие токена в FSM
        2. Если токен истек или скоро истечет - обновляет
        3. Если refresh токен истек - требует повторную авторизацию

        Args:
            state: FSM контекст пользователя
            telegram_id: Telegram ID пользователя
            force_refresh: Принудительно обновить токен

        Returns:
            Access токен или None если требуется авторизация
        """
        # Пытаемся получить сохраненные данные о токене
        token_data = await self._get_cached_token_data(state)

        # Если токена нет - пробуем получить новый через login
        if not token_data:
            logger.debug(f"Токен отсутствует для {telegram_id}, пробуем login")
            return await self._login_and_cache(state, telegram_id)

        # Если refresh токен истек - требуется повторная авторизация
        if token_data.refresh_expired:
            logger.warning(f"Refresh токен истек для пользователя {telegram_id}")
            await self._clear_token_data(state)
            return None

        # Если access токен валиден и не требует обновления
        if not force_refresh and not token_data.needs_refresh:
            logger.debug(f"Используем кэшированный токен для {telegram_id}")
            return token_data.access_token

        # Обновляем токен
        logger.info(f"Обновляем токен для пользователя {telegram_id}")
        return await self._refresh_and_cache(state, token_data)

    async def save_token_from_response(
        self, state: FSMContext, response: dict, telegram_id: int
    ) -> None:
        """
        Сохраняет токен из ответа API в FSM.

        Args:
            state: FSM контекст
            response: Ответ от /auth/by-code или /auth/login
            telegram_id: Telegram ID пользователя
        """
        try:
            # Извлекаем user_id из ответа
            user_id = response.get("user", {}).get("id")
            if not user_id:
                logger.error(f"Отсутствует user_id в ответе для {telegram_id}")
                return

            # Создаем TokenData из ответа
            token_data = TokenData.from_api_response(response, user_id)

            # Сохраняем в FSM
            await self._cache_token_data(state, token_data)

            logger.info(
                f"Токен сохранен для пользователя {telegram_id} "
                f"(истекает через {response['expires_in']}с)"
            )

        except Exception as e:
            logger.error(f"Ошибка при сохранении токена для {telegram_id}: {e}")

    async def invalidate_token(self, state: FSMContext, telegram_id: int) -> None:
        """
        Инвалидирует токен (при logout или блокировке).

        Args:
            state: FSM контекст
            telegram_id: Telegram ID пользователя
        """
        await self._clear_token_data(state)
        logger.info(f"Токен инвалидирован для пользователя {telegram_id}")

    # === Приватные методы ===

    async def _get_cached_token_data(self, state: FSMContext) -> TokenData | None:
        """Получает данные о токене из FSM"""
        try:
            data = await state.get_data()
            token_dict = data.get(self.FSM_KEY)

            if not token_dict:
                return None

            return TokenData.from_dict(token_dict)

        except Exception as e:
            logger.error(f"Ошибка при чтении токена из FSM: {e}")
            return None

    async def _cache_token_data(self, state: FSMContext, token_data: TokenData) -> None:
        """Сохраняет данные о токене в FSM"""
        try:
            await state.update_data({self.FSM_KEY: token_data.to_dict()})
        except Exception as e:
            logger.error(f"Ошибка при сохранении токена в FSM: {e}")

    async def _clear_token_data(self, state: FSMContext) -> None:
        """Удаляет данные о токене из FSM"""
        try:
            data = await state.get_data()
            if self.FSM_KEY in data:
                del data[self.FSM_KEY]
                await state.set_data(data)
        except Exception as e:
            logger.error(f"Ошибка при очистке токена из FSM: {e}")

    async def _login_and_cache(self, state: FSMContext, telegram_id: int) -> str | None:
        """
        Получает токен через login и кэширует его.

        Returns:
            Access токен или None при ошибке
        """
        try:
            result = await self.auth_client.login(telegram_id)

            if not result.success or not isinstance(result.data, dict):
                logger.warning(
                    f"Не удалось получить токен через login для {telegram_id}: "
                    f"{result.status_code} - {result.detail}"
                )
                return None

            # Сохраняем токен
            await self.save_token_from_response(state, result.data, telegram_id)

            return result.data["access_token"]

        except Exception as e:
            logger.error(f"Ошибка при login для {telegram_id}: {e}", exc_info=True)
            return None

    async def _refresh_and_cache(self, state: FSMContext, old_token_data: TokenData) -> str | None:
        """
        Обновляет токен через refresh endpoint и кэширует.

        Returns:
            Новый access токен или старый при ошибке обновления
        """
        try:
            result = await self.auth_client.refresh_token(old_token_data.refresh_token)

            if result.success and isinstance(result.data, dict):
                await self.save_token_from_response(state, result.data, old_token_data.user_id)
                return result.data["access_token"]
            else:
                logger.error(f"Не удалось обновить токен: {result.detail}")
                await self._clear_token_data(state)
                return None

        except Exception as e:
            logger.error(f"Ошибка при обновлении токена: {e}", exc_info=True)
            # При ошибке возвращаем старый токен
            return old_token_data.access_token
