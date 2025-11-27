"""
Модуль сообщений для админ-панели.

Все текстовые константы для админских функций.
"""

from typing import Final


class AdminMainMenu:
    """Сообщения главного меню администратора."""

    WELCOME: Final = "👑 Привет, администратор {name}!"

    MAIN_MENU: Final = (
        "📊 **Статистика системы**\n\n"
        "🔄 Активные заказы: {active_orders}\n"
        "👥 Активные курьеры: {active_couriers}\n"
        "📦 Заказов сегодня: {orders_today}\n"
        "⚠️ Активные споры: {active_disputes}"
    )


class AdminMainButtons:
    """Кнопки главного меню."""

    REGISTRATION_CODE: Final = "📝 Коды регистрации"
    ORDERS: Final = "📦 Заказы"
    COURIERS: Final = "🚚 Курьеры"
    SHOPS: Final = "🏪 Магазины"
    DISPUTES: Final = "⚠️ Споры"
    STATISTICS: Final = "📊 Статистика"
    EDIT_PROFILE: Final = "⚙️ Профиль"


class AdminRegistrationCodes:
    """Сообщения для работы с кодами регистрации."""

    MENU: Final = "📝 **Управление кодами регистрации**\n\nВыберите действие:"

    CREATE_PROMPT: Final = "Выберите роль для создания регистрационного кода:"

    CODE_CREATED: Final = (
        "✅ Код для роли **{role}** успешно создан!\n\n"
        "**Код:** `{code}`\n\n"
        "Отправьте этот код пользователю для регистрации."
    )

    NO_CODES_FOUND: Final = "ℹ️ Коды регистрации не найдены."

    CODES_LIST_HEADER: Final = "📋 **Список кодов регистрации**\n\nВсего: {total}"

    CODE_DETAILS: Final = (
        "🎫 **Информация о коде**\n\n"
        "**Код:** `{code}`\n"
        "**Роль:** {role}\n"
        "**Статус:** {status} {status_emoji}\n"
        "**Создан:** {created_at}\n"
        "**Истекает:** {expires_at}"
    )

    CODE_DEACTIVATED: Final = "✅ Код успешно деактивирован"

    CODE_DEACTIVATION_ERROR: Final = "❌ Ошибка деактивации кода: {detail}"


class AdminRegistrationCodesButtons:
    """Кнопки для управления кодами."""

    CREATE_CODE_FOR_COURIER: Final = "📝 Код для курьера"
    CREATE_CODE_FOR_SHOP: Final = "📝 Код для магазина"
    VIEW_REGISTRATION_CODES: Final = "📋 Просмотр кодов"
    BACK: Final = "⬅️ Назад"


class AdminKeyboard:
    """Общие кнопки админки."""

    SHOP: Final = "Магазин"
    COURIER: Final = "Курьер"
    BACK: Final = "⬅️ Назад"


class AdminService:
    """Служебные сообщения админ-сервисов."""

    UNKNOWN_ERROR: Final = "неизвестная ошибка"
    CONNECTION_ERROR: Final = "ошибка связи"
    INTERNAL_ERROR: Final = "внутренняя ошибка"

    CODES_HEADER: Final = "📋 Регистрационные коды:\n\n"
    MORE_CODES: Final = "\n… и ещё {count} кодов"

    STATS_HEADER: Final = "📊 Системная статистика:\n"
    USERS_STATS: Final = "{emoji} Пользователи: {count}"
    ADMIN_STATS: Final = "  {emoji} Админы: {count}"
    SHOPS_STATS: Final = "  {emoji} Магазины: {count}"
    COURIERS_STATS: Final = "  {emoji} Курьеры: {count}"
    ORDERS_STATS: Final = "{emoji} Заказы: {count}"
    ACTIVE_ORDERS_STATS: Final = "  {emoji} Активные: {count}"
    COMPLETED_ORDERS_STATS: Final = "  {emoji} Завершенные: {count}"
    CANCELLED_ORDERS_STATS: Final = "  {emoji} Отмененные: {count}"
    DISPUTES_STATS: Final = "{emoji} Споры: {count}"
    UNRESOLVED_DISPUTES_STATS: Final = "  {emoji} Не разрешенные: {count}"

    MESSAGE_TRUNCATED: Final = "\n\n... (сообщение обрезано)"


class AdminMessages:
    """Все сообщения админки (для совместимости)."""

    # Главное меню
    MENU = "👑 Панель администратора:\nВыберите действие:"

    # Коды регистрации
    CREATE_CODE_PROMPT = AdminRegistrationCodes.CREATE_PROMPT
    CODE_CREATED = AdminRegistrationCodes.CODE_CREATED
    LOADING_CODES = "📋 Загружаю список кодов..."
    NO_CODES_FOUND = AdminRegistrationCodes.NO_CODES_FOUND
    BROADCAST_IN_DEV = "📢 Эта функция находится в разработке."
    INVALID_ROLE = "❌ Неверная роль."
