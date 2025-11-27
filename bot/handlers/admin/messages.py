class AdminMainButtons:
    """Клавиатуры для админ-панели"""

    REGISTRATION_CODE = "Код регистрации"
    SHOPS = "Магазины"
    COURIERS = "Курьеры"
    ORDERS = "Заказы"
    DISPUTES = "Споры"
    STATISTICS = "Статистика"
    EDIT_PROFILE = "Редактировать профиль"


class AdminRegistrationCodesMenuButtons:
    """Клавиши меню 'Код регистрации' для админ-панели"""

    CREATE_CODE_FOR_COURIER = "Код для курьера"
    CREATE_CODE_FOR_SHOP = "Код для магазина"
    VIEW_REGISTRATION_CODES = "Список кодов"
    BACK = "Назад"


class AdminMessages:
    REGISTRATION_CODE_MENU = "Код регистрации позволяет зарегистрироваться новым пользователям."
    ADMIN_MAIN_MENU = """Главное меню бота:

Активные заказы: {active_orders}
Активные курьеры: {active_couriers}
Всего заказов сегодня: {orders_today}
Активные споры: {active_disputes}"""

    ORDERS_LIST_TITLE = "📋 **Список заказов**\nВсего: {total_count}"
    ORDER_DETAILS_TEMPLATE = (
        "📦 **Заказ #{id}**\n"
        "📊 **Статус:** {status}\n"
        "🏪 **Магазин:** {shop_name}\n"
        "👤 **Курьер:** {courier_name}\n"
        "💰 **Цена:** {price} сум\n"
        "📍 **Адрес:** {address}\n"
        "📅 **Создан:** {created_at}\n"
        "📝 **Тип:** {order_type}\n"
        "{extra_info}"
    )
    NO_ORDERS_FOUND = "Заказы не найдены."
    ORDER_NOT_FOUND = "Заказ не найден."
