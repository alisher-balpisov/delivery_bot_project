"""
Модуль общих сообщений.
"""

from typing import Final


class CommonMessages:
    """Общие сообщения."""

    API_TESTING: Final = "🔄 Тестирую соединение с API..."

    API_STATUS_TEMPLATE: Final = (
        "✅ API соединение успешно!\n\n"
        "🏥 Статус: {status}\n"
        "📱 Приложение: {app}\n"
        "🏷️ Версия: {version}\n"
        "🕐 Время: {timestamp}"
    )

    UNKNOWN_COMMAND: Final = (
        "👋 Неизвестная команда. Используйте /help для просмотра списка команд."
    )

    USE_HELP: Final = "Используйте /help для просмотра команд"

    STATUS_TEMPLATE: Final = "📊 Ваш статус: {status}\n{emoji} Роль: {role_name}"


class PublicMessages:
    """Сообщения для публичных команд."""

    MENU_KEYWORDS = {"меню", "команды", "помощь", "help", "menu", "commands"}
    STATUS_KEYWORDS = {"статус", "status", "мой статус", "my status"}

    HELP_HEADER: Final = "🤖 Доступные команды бота:"
    MAIN_COMMANDS: Final = "📋 Основные команды:"
    HELP_COMMAND: Final = "/help - показать эту справку"
    ME_COMMAND: Final = "/me - показать ваш профиль"

    AUTHORIZED: Final = "авторизован"
    UNAUTHORIZED: Final = "не авторизован"
    DEFAULT_EMOJI: Final = "👤"


class CourierMessages:
    """Сообщения для курьеров."""

    ACCEPT_ORDER: Final = "✅ Принять заказ"
    AVAILABLE_ORDERS_ERROR: Final = "Ошибка при получении доступных заказов: {}"
    MISSING_USER_ID: Final = "Отсутствует user_id в user_data для telegram_id: {}"
    ORDER_ALREADY_TAKEN: Final = "Заказ уже принят"
    TAKE_ORDER_CRITICAL_ERROR: Final = "Критическая ошибка при принятии заказа {} для {}: {}"
    NO_AVAILABLE_ORDERS: Final = "📭 Нет доступных заказов."
    INVALID_ORDER_ID_ERROR: Final = "Ошибка: Неверный ID заказа."


class ShopMessages:
    """Сообщения для магазинов."""

    CONFIRM_ORDER: Final = "✅ Подтвердить заказ"
    CANCEL_ORDER: Final = "❌ Отменить"
    UNKNOWN_ERROR: Final = "неизвестная ошибка"
    CREATE_ORDER_CRITICAL_ERROR: Final = "Критическая ошибка при создании заказа: {}"


class DisputeMessages:
    """Сообщения, связанные со спорами."""

    LOADING_DISPUTES: Final = "⚠️ Загружаю ваши споры..."
    NO_DISPUTES: Final = "⚠️ У вас нет активных споров."
    DISPUTES_HEADER: Final = "⚠️ **Ваши споры:**\n"

    NEW_DISPUTE_PROMPT: Final = (
        "⚠️ **Открыть спор:**\n\n"
        "Если с доставкой возникли проблемы, отправьте ID заказа для открытия спора.\n"
        "Пример: /dispute 123\n\n"
        "Статус: {status} (будет установлен автоматически)"
    )


class CommonServiceMessages:
    """Служебные сообщения (восстановлено для совместимости)."""

    API_STATUS_ERROR: Final = "Ошибка получения статуса API"
    UNEXPECTED_ERROR: Final = "Неожиданная ошибка: {}"

    SHOP_ORDERS: Final = "{} Заказы магазина"
    COURIER_ORDERS: Final = "{} Заказы курьера"
    ADMIN_ORDERS: Final = "{} Заказы администратора"

    DISPUTE_STATUS_OPEN: Final = "🟢 Открыт"
    DISPUTE_STATUS_IN_REVIEW: Final = "🟡 На рассмотрении"
    DISPUTE_STATUS_RESOLVED: Final = "✅ Решен"
    DISPUTE_STATUS_CLOSED: Final = "⚫️ Закрыт"
    DISPUTE_STATUS_DEFAULT: Final = "❓ Неизвестно"

    DISPUTE_LINE: Final = "🆔 `{id}` | {status} | {created_at}"
    DISPUTES_ERROR: Final = "Ошибка при получении споров: {}"
