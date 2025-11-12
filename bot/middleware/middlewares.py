"""
Middleware для Telegram-бота.

Этот модуль содержит middleware для:
- Логирования всех событий
- Rate limiting (защита от спама)
- Обработки ошибок
"""

from collections import defaultdict
from collections.abc import Callable
from time import time
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from backend.src.core.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логирования всех входящих событий.

    Логирует:
    - Тип события (message, callback, etc.)
    - ID пользователя и его username
    - Текст сообщения или callback_data
    - Время обработки
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Any],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Получаем информацию о событии
        event_type = type(event).__name__
        user_info = self._get_user_info(event)
        event_details = self._get_event_details(event)

        # Логируем начало обработки
        logger.info(f"→ {event_type} от пользователя {user_info}: {event_details}")

        # Замеряем время выполнения
        start_time = time()

        try:
            # Выполняем обработчик
            result = await handler(event, data)

            # Логируем успешное завершение
            duration_ms = (time() - start_time) * 1000
            logger.info(f"✓ {event_type} обработан за {duration_ms:.2f}ms")

            return result

        except Exception as e:
            # Логируем ошибку
            duration_ms = (time() - start_time) * 1000
            logger.error(
                f"✗ Ошибка при обработке {event_type} (за {duration_ms:.2f}ms): {e}", exc_info=True
            )
            raise

    def _get_user_info(self, event: TelegramObject) -> str:
        """Извлекает информацию о пользователе из события"""
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
            username = f"@{user.username}" if user.username else "без username"
            return f"{user.id} ({user.first_name} {username})"
        return "неизвестный"

    def _get_event_details(self, event: TelegramObject) -> str:
        """Извлекает детали события для логирования"""
        if isinstance(event, Message):
            if event.text:
                text = event.text[:50]
                return f"текст: '{text}...'" if len(event.text) > 50 else f"текст: '{text}'"
            elif event.photo:
                return "фото"
            elif event.document:
                return "документ"
            return "другое содержимое"

        elif isinstance(event, CallbackQuery):
            data = event.data or ""
            return f"callback: '{data[:30]}...'" if len(data) > 30 else f"callback: '{data}'"

        return "нет деталей"


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов (rate limiting).

    Защищает от спама, ограничивая количество сообщений от одного пользователя
    в определенный промежуток времени.

    Args:
        limit: Максимальное количество запросов в окне
        window: Временное окно в секундах
    """

    def __init__(self, limit: int = 30, window: int = 60):
        super().__init__()
        self.limit = limit
        self.window = window
        # Храним временные метки запросов для каждого пользователя
        self.users: dict[int, list[float]] = defaultdict(list)
        # Временные метки последних предупреждений (чтобы не спамить)
        self.warned_users: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Any],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Получаем user_id
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)

        now = time()

        # Очищаем старые запросы (вне окна)
        self.users[user_id] = [
            timestamp for timestamp in self.users[user_id] if now - timestamp < self.window
        ]

        # Проверяем лимит
        if len(self.users[user_id]) >= self.limit:
            # Проверяем, не предупреждали ли мы недавно
            last_warning = self.warned_users.get(user_id, 0)
            if now - last_warning > 10:  # Предупреждаем раз в 10 секунд
                await self._send_rate_limit_message(event)
                self.warned_users[user_id] = now
                logger.warning(
                    f"Rate limit превышен для пользователя {user_id}: "
                    f"{len(self.users[user_id])} запросов за {self.window}с"
                )
            return None  # Блокируем обработку

        # Добавляем текущий запрос
        self.users[user_id].append(now)

        return await handler(event, data)

    def _get_user_id(self, event: TelegramObject) -> int | None:
        """Извлекает user_id из события"""
        if isinstance(event, (Message, CallbackQuery)):
            return event.from_user.id
        return None

    async def _send_rate_limit_message(self, event: TelegramObject) -> None:
        """Отправляет предупреждение о превышении лимита"""
        message = (
            f"⏱ Вы отправляете слишком много запросов.\nПожалуйста, подождите {self.window} секунд."
        )

        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception as e:
            logger.error(f"Не удалось отправить rate limit сообщение: {e}")


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware для централизованной обработки ошибок.

    Перехватывает все исключения и отправляет пользователю
    понятное сообщение вместо падения бота.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Any],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)

        except Exception as e:
            # Логируем ошибку
            logger.exception(f"Необработанная ошибка в middleware: {e}")

            # Отправляем пользователю сообщение об ошибке
            await self._send_error_message(event)

            # Можно отправить уведомление админам
            await self._notify_admins(event, e, data)

            # Не пробрасываем исключение дальше
            return None

    async def _send_error_message(self, event: TelegramObject) -> None:
        """Отправляет пользователю сообщение об ошибке"""
        message = (
            "😔 Произошла непредвиденная ошибка.\n"
            "Мы уже работаем над её исправлением.\n\n"
            "Попробуйте повторить позже или используйте /help"
        )

        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
                if event.message:
                    await event.message.answer(message)
        except Exception as e:
            logger.warning(f"Не удалось отправить пользователю сообщение об ошибке: {e}")

    async def _notify_admins(
        self, event: TelegramObject, error: Exception, data: dict[str, Any]
    ) -> None:
        """Отправляет уведомление администраторам о критической ошибке"""
        try:
            from backend.src.core.config import settings

            # Формируем сообщение
            user_id = None
            if isinstance(event, (Message, CallbackQuery)):
                user_id = event.from_user.id

            notification = (
                "🚨 <b>Критическая ошибка в боте</b>\n\n"
                f"<b>Тип:</b> {type(error).__name__}\n"
                f"<b>Сообщение:</b> {str(error)[:200]}\n"
                f"<b>Пользователь:</b> {user_id}\n"
                f"<b>Событие:</b> {type(event).__name__}"
            )

            # Получаем бота из data
            bot = data.get("bot")
            if not bot:
                return

            # Отправляем всем админам
            for admin_id in settings.admin.super_admin_telegram_ids:
                try:
                    await bot.send_message(admin_id, notification, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Не удалось уведомить администратора {admin_id=}: {e}")

        except Exception as e:
            logger.error(f"Не удалось уведомить администраторов: {e}")


class UserActivityMiddleware(BaseMiddleware):
    """
    Middleware для отслеживания активности пользователей.

    Может использоваться для:
    - Обновления last_seen в базе данных
    - Сбора статистики использования
    - Аналитики поведения пользователей
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Any],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Получаем информацию о пользователе
        user_id = self._get_user_id(event)
        if user_id:
            # Обновляем активность (можно отправить в Redis или БД)
            await self._update_user_activity(user_id, event, data)

        return await handler(event, data)

    def _get_user_id(self, event: TelegramObject) -> int | None:
        """Извлекает user_id из события"""
        if isinstance(event, (Message, CallbackQuery)):
            return event.from_user.id
        return None

    async def _update_user_activity(
        self, user_id: int, event: TelegramObject, data: dict[str, Any]
    ) -> None:
        """
        Обновляет информацию об активности пользователя.

        Здесь можно:
        - Записать в Redis с TTL
        - Обновить timestamp в БД
        - Отправить событие в аналитику
        """
        # Пример с логированием (в продакшене - запись в БД/Redis)
        event_type = type(event).__name__
        logger.debug(f"Активность пользователя {user_id}: {event_type}")

        # TODO: Реализовать запись в БД или Redis
        # Пример:
        # redis_client = data.get('redis_client')
        # await redis_client.setex(
        #     f"user_activity:{user_id}",
        #     3600,  # TTL 1 час
        #     time()
        # )


# Функция для регистрации всех middleware
def setup_middlewares(dispatcher) -> None:
    """
    Регистрирует все middleware в правильном порядке.

    Порядок важен:
    1. Логирование (первым - чтобы залогировать все)
    2. Rate limiting (защита от спама)
    3. User activity (отслеживание)
    4. Error handler (последним - ловит все ошибки)
    """
    # Для message
    dispatcher.message.middleware(LoggingMiddleware())
    dispatcher.message.middleware(RateLimitMiddleware(limit=30, window=60))
    dispatcher.message.middleware(UserActivityMiddleware())
    dispatcher.message.middleware(ErrorHandlerMiddleware())

    # Для callback_query
    dispatcher.callback_query.middleware(LoggingMiddleware())
    dispatcher.callback_query.middleware(RateLimitMiddleware(limit=50, window=60))
    dispatcher.callback_query.middleware(UserActivityMiddleware())
    dispatcher.callback_query.middleware(ErrorHandlerMiddleware())

    logger.info("✅ Middleware зарегистрированы")
