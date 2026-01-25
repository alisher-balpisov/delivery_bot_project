import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger

from bot.clients.auth_client import AuthClient
from bot.dto import UserDTO
from bot.redis_storage import UserCacheData, UserDataStorage

logger = get_logger(__name__)


class TokenRefreshMiddleware(BaseMiddleware):
    """
    Middleware для автоматического обновления токенов.

    Логика работы:
    1. Проверяет, нужно ли обновить токен (за 5 минут до истечения)
    2. Если нужно и refresh токен валиден - обновляет токены
    3. Если refresh токен истек - логаутит пользователя
    4. Использует locks для предотвращения параллельных refresh запросов
    """

    def __init__(self, storage: UserDataStorage, auth_client: AuthClient):
        """
        Инициализирует middleware.

        Args:
            storage: UserDataStorage для работы с Redis
            auth_client: AuthClient для обновления токенов
        """
        self.storage = storage
        self.auth_client = auth_client
        # Локи для предотвращения параллельных refresh для одного пользователя
        self._refresh_locks: dict[int, asyncio.Lock] = {}
        self._lock_cleanup_task: asyncio.Task | None = None
        # Хранилище для активных фоновых задач (чтобы избежать garbage collection)
        self._active_refresh_tasks: set[asyncio.Task] = set()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Основная логика middleware"""

        # Получаем пользователя и полные данные из data
        user: UserDTO | None = data.get("user")
        user_data: UserCacheData | None = data.get("user_data")

        # Обрабатываем только аутентифицированных пользователей
        if user and user.role != UserRole.GUEST and user.telegram_id and user_data:
            await self._check_and_refresh_token(user_data, data)

        # Продолжаем обработку
        return await handler(event, data)

    async def _check_and_refresh_token(
        self, user_data: UserCacheData, data: dict[str, Any]
    ) -> None:
        """
        Проверяет необходимость обновления токена и обновляет его если нужно.

        Args:
            user_data: Полные данные пользователя из Redis (уже загружены в фильтре)
            data: Словарь данных для хендлера (может обновить user)
        """
        try:
            telegram_id = user_data.telegram_id

            # Проверяем, нужно ли обновлять токен
            if not user_data.needs_token_refresh:
                logger.debug(f"Токен пользователя {telegram_id} не требует обновления")
                return

            # Проверяем валидность refresh токена
            if not user_data.refresh_token_valid:
                logger.warning(f"Refresh токен пользователя {telegram_id} истек, выполняем logout")
                await self._handle_expired_refresh_token(telegram_id, data)
                return

            # ОПТИМИЗАЦИЯ: Если токен еще валиден (хотя и близок к истечению),
            # выполняем обновление фоном, не блокируя хендлер.
            if user_data.has_valid_token:
                logger.info(f"Запуск фонового обновления токена для {telegram_id}")
                task = asyncio.create_task(
                    self._refresh_token_with_lock(telegram_id, user_data, data)
                )
                self._active_refresh_tasks.add(task)
                task.add_done_callback(self._active_refresh_tasks.discard)
            else:
                # Если токен уже истек - блокируем и ждем обновления
                logger.info(f"Срочное (блокирующее) обновление токена для {telegram_id}")
                await self._refresh_token_with_lock(telegram_id, user_data, data)

        except Exception as e:
            logger.error(
                f"Ошибка при проверке/обновлении токена для {user_data.telegram_id}: {e}",
                exc_info=True,
            )

    async def _refresh_token_with_lock(
        self, telegram_id: int, user_data: UserCacheData, data: dict[str, Any]
    ) -> None:
        """
        Обновляет токен с использованием lock для предотвращения race conditions.

        Args:
            telegram_id: ID пользователя
            user_data: Текущие данные пользователя
            data: Словарь данных для хендлера
        """
        # Получаем или создаем lock для пользователя
        if telegram_id not in self._refresh_locks:
            self._refresh_locks[telegram_id] = asyncio.Lock()

        lock = self._refresh_locks[telegram_id]

        # Если кто-то уже обновляет токен - ждем (только если мы в блокирующем режиме)
        # Если мы в фоновом режиме (через create_task), то lock.locked() просто вернет управление.
        if lock.locked():
            logger.debug(f"Refresh токена для {telegram_id} уже выполняется, ожидаем")
            async with lock:
                # После ожидания проверяем, не обновили ли уже токен
                updated_data = await self.storage.get_user_data(telegram_id)
                if updated_data and not updated_data.needs_token_refresh:
                    logger.debug(f"Токен для {telegram_id} уже был обновлен другим запросом")
                    return

        # Выполняем refresh
        async with lock:
            logger.info(f"Начинаем обновление токена для пользователя {telegram_id}")

            result = await self.auth_client.refresh_token(user_data.refresh_token)

            if result.success and result.data:
                # Сохраняем новые токены
                success = await self.storage.save_tokens(
                    telegram_id=telegram_id,
                    access_token=result.data["access_token"],
                    refresh_token=result.data.get("refresh_token", user_data.refresh_token),
                    access_expires_in=result.data["expires_in"],
                    refresh_expires_in=result.data.get(
                        "refresh_expires_in",
                        int(
                            user_data.refresh_expires_at.timestamp()
                            if user_data.refresh_expires_at
                            else 86400
                        ),
                    ),
                )

                if success:
                    # ВАЖНО: Обновляем объект user_data in-place
                    # Это необходимо, чтобы:
                    # 1. Текущий запрос использовал новый (валидный) токен
                    # 2. L1 кэш в UserDataFilter (который хранит ссылку на этот объект)
                    #    автоматически обновился и не отдавал старые данные
                    now = datetime.now(UTC)
                    user_data.access_token = result.data["access_token"]
                    user_data.refresh_token = result.data.get(
                        "refresh_token", user_data.refresh_token
                    )
                    user_data.token_expires_at = now + timedelta(seconds=result.data["expires_in"])

                    refresh_in = result.data.get("refresh_expires_in")
                    if refresh_in:
                        user_data.refresh_expires_at = now + timedelta(seconds=refresh_in)

                    logger.info(f"Токены успешно обновлены для пользователя {telegram_id}")
                else:
                    logger.error(f"Не удалось сохранить обновленные токены для {telegram_id}")

            elif result.status_code == 401:
                # Refresh токен недействителен
                logger.warning(f"Refresh токен недействителен для {telegram_id}, выполняем logout")
                await self._handle_expired_refresh_token(telegram_id, data)

            else:
                # Другая ошибка
                logger.error(
                    f"Не удалось обновить токен для {telegram_id}: "
                    f"{result.detail or 'Unknown error'}"
                )

    async def _handle_expired_refresh_token(self, telegram_id: int, data: dict[str, Any]) -> None:
        """
        Обрабатывает ситуацию истекшего refresh токена.

        Действия:
        1. Удаляет данные пользователя из Redis
        2. Обновляет UserDTO в data на гостя
        3. Помечает, что нужно показать сообщение о необходимости повторного входа

        Args:
            telegram_id: ID пользователя
            data: Словарь данных для хендлера
        """
        # Удаляем данные из Redis
        await self.storage.delete_user_data(telegram_id)

        # Обновляем UserDTO в data на гостя
        guest_user = UserDTO(
            user_id=None,
            telegram_id=telegram_id,
            name=None,
            role=UserRole.GUEST,
        )

        data["user"] = guest_user

        # Помечаем, что нужно показать сообщение о необходимости повторного входа
        data["token_expired"] = True

        logger.info(
            f"Пользователь {telegram_id} конвертирован в гостя из-за истекшего refresh токена"
        )

    async def start_cleanup_task(self) -> None:
        """Запускает фоновую задачу очистки старых locks"""
        if self._lock_cleanup_task is None or self._lock_cleanup_task.done():
            self._lock_cleanup_task = asyncio.create_task(self._cleanup_old_locks())
            logger.info("Запущена задача очистки старых locks")

    async def _cleanup_old_locks(self) -> None:
        """Периодически очищает неиспользуемые locks"""
        while True:
            try:
                await asyncio.sleep(300)  # Каждые 5 минут

                # Удаляем незалоченные locks
                to_remove = [tid for tid, lock in self._refresh_locks.items() if not lock.locked()]

                for tid in to_remove:
                    del self._refresh_locks[tid]

                if to_remove:
                    logger.debug(f"Удалено {len(to_remove)} неактивных locks")

            except asyncio.CancelledError:
                logger.info("Задача очистки locks остановлена")
                break
            except Exception as e:
                logger.error(f"Ошибка в задаче очистки locks: {e}", exc_info=True)

    async def stop_cleanup_task(self) -> None:
        """Останавливает фоновую задачу"""
        if self._lock_cleanup_task and not self._lock_cleanup_task.done():
            self._lock_cleanup_task.cancel()
            try:
                await self._lock_cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Задача очистки locks остановлена")
