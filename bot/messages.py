from typing import ClassVar

from backend.src.common.enums import UserRole

from bot.constants import ROLE_EMOJI_MAP


class AdminKeyboardMessages:
    """Сообщения для клавиатур в админ-панели."""

    CREATE_CODE = "📝 Создать код"
    VIEW_CODES = "📋 Просмотр кодов"
    STATS = "📊 Статистика"
    SHOP = "Магазин"
    COURIER = "Курьер"
    BACK = "⬅️ Назад"


class AdminMessages:
    """Сообщения для админ-панели."""

    MENU = f"{ROLE_EMOJI_MAP[UserRole.ADMIN]} Панель администратора:\\Выберите действие:"
    CREATE_CODE_PROMPT = "📝 Выберите роль для создания регистрационного кода:"
    CODE_CREATED = "✅ Код для роли {} создан: `{}`"
    LOADING_CODES = "📋 Загружаю список кодов..."
    NO_CODES_FOUND = "ℹ️ Активных кодов регистрации не найдено."
    BROADCAST_IN_DEV = "📢 Эта функция находится в разработке."
    INVALID_ROLE = "❌ Неверная роль."


class AdminServiceMessages:
    """Сообщения для сервиса в админ-панели."""

    UNKNOWN_ERROR = "неизвестная ошибка"
    CONNECTION_ERROR = "ошибка связи"
    INTERNAL_ERROR = "внутренняя ошибка"
    CODE_TABLE_HEADER = f"{'Код':<12}{'Роль':<12}{'Статус':<15}"
    USED = "использован"
    NOT_USED = "не использован"
    CODES_HEADER = "📋 Регистрационные коды:\n\n<pre>"
    CODES_FOOTER = "</pre>"
    MORE_CODES = "\n… и ещё {} кодов"
    STATS_HEADER = "📊 Системная статистика:\n"
    USERS_STATS = "{} Пользователи: {}"
    ADMIN_STATS = "  {} Админы: {}"
    SHOPS_STATS = "  {} Магазины: {}"
    COURIERS_STATS = "  {} Курьеры: {}"
    ORDERS_STATS = "{} Заказы: {}"
    ACTIVE_ORDERS_STATS = "  {} Активные: {}"
    COMPLETED_ORDERS_STATS = "  {} Завершенные: {}"
    CANCELLED_ORDERS_STATS = "  {} Отмененные: {}"
    DISPUTES_STATS = "{} Споры: {}"
    UNRESOLVED_DISPUTES_STATS = "  {} Не разрешенные: {}"
    MESSAGE_TRUNCATED = "\n\n... (сообщение обрезано)"


class AuthServiceMessages:
    """Сообщения для сервиса в админ-панели."""

    UNKNOWN_ROLE = "Получена неизвестная роль '{} ' от API. Присвоена роль GUEST."
    STATE_UPDATED = "Обновлены данные в FSM для пользователя {} "
    UNKNOWN_ERROR = "Неизвестная ошибка"
    ACTIVE = "активен"
    DEACTIVATED = "деактивирован"
    YES = "да"
    NO = "нет"
    NOT_SPECIFIED = "не указано"
    UNEXPECTED_ERROR = "Неожиданная ошибка в get_user_stats_text: {} "
    START_COMMAND_ERROR = "Ошибка при обработке команды /start для {}: {} "
    REGISTRATION_CRITICAL_ERROR = "Критическая ошибка при регистрации {} "
    GENERIC_ERROR = "Произошла ошибка. Попробуйте позже."
    CRITICAL_REGISTRATION_ERROR = "Произошла критическая ошибка при регистрации."


class CommonServiceMessages:
    """Сообщения для общего сервиса."""

    API_STATUS_ERROR = "не удалось получить статус"
    UNEXPECTED_ERROR = "Неожиданная ошибка в get_api_status_text: {} "
    SHOP_ORDERS = "{} Ваши заказы:\n\n📦 Создайте новый заказ командой /new_order"
    COURIER_ORDERS = "{} Назначенные заказы:\n\n🚚 Доступные заказы появятся здесь"
    ADMIN_ORDERS = (
        "{} Управление заказами:\n\n⚙️ Все заказы системы доступны в панели администратора"
    )
    DISPUTE_STATUS_OPEN = "🟡"
    DISPUTE_STATUS_IN_REVIEW = "🟠"
    DISPUTE_STATUS_RESOLVED = "🟢"
    DISPUTE_STATUS_CLOSED = "🔴"
    DISPUTE_STATUS_DEFAULT = "⚪"
    DISPUTE_LINE = "{:04d} {} {} "
    DISPUTES_ERROR = "Ошибка при получении споров для telegram_id={}: {} "


class CourierMessages:
    """Сообщения для курьера."""

    ACCEPT_ORDER = "✅ Принять заказ"
    AVAILABLE_ORDERS_ERROR = "Ошибка при получении доступных заказов для {}: {} "
    MISSING_USER_ID = "Отсутствует user_id в user_data для telegram_id: {} "
    ORDER_ALREADY_TAKEN = "Заказ уже принят"
    TAKE_ORDER_CRITICAL_ERROR = "Критическая ошибка при принятии заказа {} для {}: {} "
    NO_AVAILABLE_ORDERS = "📭 Нет доступных заказов."
    INVALID_ORDER_ID_ERROR = "Ошибка: Неверный ID заказа."


class AuthMessages:
    """Сообщения для процесса аутентификации и регистрации."""

    WELCOME_NEW_USER = "Добро пожаловать! Для регистрации в системе используйте команду /register"
    WELCOME_ADMIN = "Добро пожаловать, администратор!\nЧтобы посмотреть команды /help"
    WELCOME_AUTHENTICATED = (
        "Добро пожаловать! Вы успешно авторизованы ✅\nЧтобы посмотреть команды /help"
    )
    ENTER_CODE = "📝 Введите ваш код приглашения:"
    CHECKING_CODE = "🔄 Проверяю код..."
    ALREADY_REGISTERED = "ℹ️ Вы уже зарегистрированы"
    SUCCESS = "✅ Регистрация успешна {}\nНажмите /start чтобы начать"
    BLOCKED = "Вы заблокированы. Доступ запрещён."
    INVALID_CODE_ATTEMPTS = "Неверный код. Осталось попыток: {} "
    INVALID_CODE = "Неверный код. Попробуйте еще раз."
    LOGOUT_SUCCESS = "✅ Вы успешно вышли из системы."
    NOT_LOGGED_IN = "Вы и так не авторизованы."
    ME_LOADING = "📊 Получаю вашу статистику..."
    ME_STATS_TEMPLATE = (
        "📈 Ваша статистика:\n\n"
        "🆔 ID: {id}\n"
        "👤 Имя: {name}\n"
        "{emoji} Роль: {role}\n"
        "📱 Telegram ID: {telegram_id}\n"
        "✨ Статус: {status}\n"
        "🚫 Блокировка: {is_blocked}"
    )


class OrderMessages:
    """Сообщения, связанные с заказами."""

    # Процесс создания
    STEP_1_DESCRIPTION = (
        "📦 Создание нового заказа\n\nШаг 1/4: Введите описание заказа (что нужно доставить):"
    )
    STEP_2_PICKUP = "Шаг 2/4: Введите адрес забора товара:"
    STEP_3_DELIVERY = "Шаг 3/4: Введите адрес доставки:"
    STEP_4_PRICE = "Шаг 4/4: Введите стоимость доставки (в тенге):"
    CONFIRMATION_PROMPT = (
        "📋 Подтвердите заказ:\n\n"
        "📦 Описание: {description}\n"
        "📍 Забор: {pickup_address}\n"
        "🎯 Доставка: {delivery_address}\n"
        "💰 Цена: {price} ₸\n"
    )
    CREATING_ORDER = "🔄 Создаю заказ..."
    SUCCESSFULLY_CREATED = "✅ Заказ #{}\n\nОжидайте, когда курьер примет заказ."

    # Просмотр и принятие
    NO_AVAILABLE_ORDERS = "📭 Нет доступных заказов."
    ORDER_ACCEPTED = (
        "✅ Вы приняли заказ #{}\nИспользуйте /my_orders для просмотра активных заказов."
    )
    AVAILABLE_ORDER_TEMPLATE = (
        "📦 Заказ #{order_id}\n"
        "📍 Откуда: {pickup_address}\n"
        "🎯 Куда: {delivery_address}\n"
        "💰 Оплата: {price} ₸\n"
    )


class CommonMessages:
    """Общие сообщения и команды."""

    API_TESTING = "🔄 Тестирую соединение с API..."
    API_STATUS_TEMPLATE = (
        "✅ API соединение успешно!\n\n"
        "🏥 Статус: {status}\n"
        "📱 Приложение: {app}\n"
        "🏷️ Версия: {version}\n"
        "🕐 Время: {timestamp}"
    )
    UNKNOWN_COMMAND = "👋 Неизвестная команда. Используйте /help для просмотра списка команд."
    USE_HELP = "Используйте /help для просмотра команд"
    STATUS_TEMPLATE = "📊 Ваш статус: {status}\n{emoji} Роль: {role_name}"


class DisputeMessages:
    """Сообщения для системы споров."""

    LOADING_DISPUTES = "⚠️ Загружаю ваши споры..."
    NO_DISPUTES = "⚠️ У вас нет активных споров."
    DISPUTES_HEADER = "⚠️ Ваши споры:\n"
    NEW_DISPUTE_PROMPT = (
        "⚠️ Открыть спор:\n\n"
        "Если с доставкой возникли проблемы, отправьте ID заказа для открытия спора.\n"
        "Пример: /dispute 123\n\n"
        "Статус: {status} (будет установлен автоматически)"
    )


class BaseClientMessages:
    """Сообщения для базового клиента API."""

    INVALID_JSON = "Не удалось распарсить ответ как JSON"
    CLIENT_ERROR = "Ошибка клиента: {}"
    HTTP_ERROR = "HTTP ошибка {} на {}: {}"
    SERVER_ERROR_RETRY = "Серверная ошибка {} - попытка {} из {}"
    UNEXPECTED_STATUS = "Неожиданный статус {} на {}"
    SERVER_ERROR = "Серверная ошибка: {}"
    TIMEOUT_RETRY = "Таймаут на {} - попытка {} из {}"
    TIMEOUT_ERROR = "Таймаут при {} {}"
    TIMEOUT_EXCEEDED = "Таймаут превышен"
    NETWORK_ERROR_RETRY = "Сетевая ошибка на {} - попытка {} из {}"
    NETWORK_ERROR = "Сетевая ошибка при {} {}: {}"
    NETWORK_ERROR_SIMPLE = "Сетевая ошибка"
    UNEXPECTED_REQUEST_ERROR = "Неожиданная ошибка запроса при {} {}: {}"
    UNEXPECTED_CLIENT_ERROR = "Неожиданная ошибка клиента"
    RETRIES_EXCEEDED = "Превышено количество попыток"


class PublicMessages:
    """Сообщения для публичных обработчиков."""

    # Ключевые слова для меню
    MENU_KEYWORDS: ClassVar = {"меню", "команды", "помощь", "help", "menu", "commands"}

    # Ключевые слова для статуса
    STATUS_KEYWORDS: ClassVar = {"статус", "status", "мой статус", "my status"}

    # Сообщения для справки
    HELP_HEADER = "🤖 Доступные команды бота:"
    MAIN_COMMANDS = "📋 Основные команды:"
    HELP_COMMAND = "/help - показать эту справку"
    ME_COMMAND = "/me - показать ваш статус"

    # Статусы авторизации
    AUTHORIZED = "авторизован"
    UNAUTHORIZED = "не авторизован"
    DEFAULT_EMOJI = "👤"


class ShopMessages:
    """Сообщения для магазина (создания заказов)."""

    # Кнопки подтверждения заказа
    CONFIRM_ORDER = "✅ Подтвердить заказ"
    CANCEL_ORDER = "❌ Отменить"

    # Сообщения об ошибках
    UNKNOWN_ERROR = "неизвестная ошибка"
    CREATE_ORDER_CRITICAL_ERROR = "Критическая ошибка при создании заказа telegram_id={}: {}"
