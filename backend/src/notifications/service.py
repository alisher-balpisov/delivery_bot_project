"""
Сервис уведомлений для Delivery Bot.

Обеспечивает отправку уведомлений пользователям о различных событиях:
- Изменение статуса заказов
- Назначение курьера на заказ
- Создание споров
- Системные уведомления

Поддерживает асинхронную отправку через Telegram Bot API с повторными попытками.
Логирует все уведомления для отслеживания отправленных сообщений.
"""

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from src.core.config import settings
from src.core.logging import get_logger
from src.models.user import User

logger = get_logger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений пользователям."""

    def __init__(self, bot: Bot | None = None):
        """
        Инициализация сервиса уведомлений.

        Args:
            bot: Экземпляр Telegram бота (опционально для тестирования)
        """
        self.bot = bot
        self.max_retries = settings.business.notification_retry_attempts
        self.retry_delay = settings.business.notification_retry_delay

    def set_bot(self, bot: Bot) -> None:
        """
        Установить экземпляр бота для сервиса.

        Args:
            bot: Экземпляр Telegram бота из aiogram
        """
        self.bot = bot
        logger.info("🤖 Telegram бот успешно подключен к сервису уведомлений")

    async def send_bulk_notifications(
        self,
        users: list[User],
        message: str,
        parse_mode: str = settings.telegram.parse_mode,
    ) -> dict[str, bool]:
        """
        Массовая отправка уведомлений.

        Args:
            users: Список получателей
            message: Текст уведомления
            parse_mode: Режим форматирования

        Returns:
            Словарь с результатами отправки
        """
        results = {}
        for user in users:
            success = await self.send_notification(user, message, parse_mode)
            results[str(user.id)] = success

        logger.info(
            f"📊 Массовые уведомления: {sum(results.values())}/{len(users)} успешно отправлены"
        )
        return results

    async def send_notification(
        self,
        user: User,
        message: str,
        parse_mode: str = settings.telegram.parse_mode,
    ) -> bool:
        """
        Отправка уведомления пользователю с повторными попытками.

        Args:
            user: Получатель уведомления
            message: Текст уведомления
            parse_mode: Режим форматирования

        Returns:
            True, если уведомление отправлено успешно
        """
        if not user.telegram_id:
            logger.warning(f"❌ У пользователя {user.id} отсутствует telegram_id")
            return False

        if not self.bot:
            logger.warning("❌ Telegram бот недоступен для отправки уведомлений")
            logger.info(f"📧 Notification to user {user.id}: {message}")
            return True

        return await self._send_to_telegram(user.telegram_id, message, parse_mode)

    async def _send_to_telegram(self, telegram_id: int, message: str, parse_mode: str) -> bool:
        """
        Внутренняя функция отправки через Telegram API.

        Args:
            telegram_id: Telegram ID получателя
            message: Текст сообщения
            parse_mode: Режим форматирования

        Returns:
            True при успешной отправке
        """
        for attempt in range(self.max_retries):
            try:
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=settings.telegram.disable_web_page_preview,
                )
                logger.info(f"✅ Уведомление отправлено пользователю {telegram_id}")
                return True

            except TelegramRetryAfter as e:
                wait_time = e.retry_after
                logger.warning(f"⏰ Retry after {wait_time}s для {telegram_id}")
                await asyncio.sleep(wait_time)

            except TelegramBadRequest as e:
                logger.error(f"❌ Ошибка Telegram API для {telegram_id}: {e}")
                break

            except Exception as e:
                logger.error(f"❌ Неизвестная ошибка при отправке уведомления: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"❌ Не удалось отправить уведомление после {self.max_retries} попыток"
                    )

        return False

    async def notify_order_status_changed(
        self, user: User, order_id: int, new_status: str, **kwargs
    ) -> bool:
        """
        Уведомление об изменении статуса заказа.

        Args:
            user: Получатель уведомления
            order_id: ID заказа
            new_status: Новый статус
            **kwargs: дополнительные параметры

        Returns:
            True при успешной отправке
        """
        emoji = self._get_status_emoji(new_status)
        message = (
            f"{emoji} <b>Статус заказа изменен</b>\n\n"
            f"📦 Заказ №{order_id}\n"
            f"📊 Новый статус: <b>{new_status}</b>"
        )

        return await self.send_notification(user, message)

    async def notify_order_assigned(
        self, user: User, order_id: int, courier_name: str, pickup_time: str
    ) -> bool:
        """
        Уведомление о назначении курьера на заказ.

        Args:
            user: Получатель уведомления
            order_id: ID заказа
            courier_name: Имя курьера
            pickup_time: Время забора

        Returns:
            True при успешной отправке
        """
        message = (
            "🚚 <b>Курьер назначен!</b>\n\n"
            f"📦 Заказ №{order_id}\n"
            f"👤 Курьер: {courier_name}\n"
            f"🕐 Время забора: {pickup_time}"
        )

        return await self.send_notification(user, message)

    async def notify_order_delivered(self, user: User, order_id: int, delivered_at: str) -> bool:
        """
        Уведомление о доставке заказа.

        Args:
            user: Получатель уведомления
            order_id: ID заказа
            delivered_at: Время доставки

        Returns:
            True при успешной отправке
        """
        message = (
            f"✅ <b>Заказ доставлен!</b>\n\n📦 Заказ №{order_id}\n🕐 Время доставки: {delivered_at}"
        )

        return await self.send_notification(user, message)

    async def notify_system_message(
        self, user: User, title: str, content: str, priority: str = "normal"
    ) -> bool:
        """
        Системное уведомление.

        Args:
            user: Получатель уведомления
            title: Заголовок
            content: Содержание
            priority: Приоритет (high, normal, low)

        Returns:
            True при успешной отправке
        """
        emoji_priority = {"high": "🔴", "normal": "📢", "low": "ℹ️"}.get(priority, "📢")
        message = f"{emoji_priority} <b>{title}</b>\n\n{content}"

        return await self.send_notification(user, message)

    def _get_status_emoji(self, status: str) -> str:
        """Получить emoji для статуса заказа."""
        status_emojis = {
            "created": "🛍️",
            "accepted": "🔄",
            "picking_up": "📤",
            "in_progress": "🚚",
            "delivered": "✅",
            "completed": "🏁",
            "cancelled": "❌",
            "disputed": "⚠️",
        }
        return status_emojis.get(status.lower(), "📊")


async def initialize_notification_service(app_state) -> None:
    """
    Инициализировать сервис уведомлений с ботом из приложения.

    Args:
        app_state: FastAPI app.state с ботом
    """
    if hasattr(app_state, "bot") and app_state.bot:
        notification_service.set_bot(app_state.bot)
        logger.info("✅ Сервис уведомлений инициализирован с ботом")
    else:
        logger.warning("⚠️ Бот недоступен при инициализации сервиса уведомлений")


def get_notification_service() -> NotificationService:
    """
    Получить глобальный экземпляр сервиса уведомлений.
    """
    return notification_service


# Глобальный экземпляр сервиса (можно инициализировать с ботом при запуске)
notification_service = NotificationService()
