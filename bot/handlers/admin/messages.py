class AdminMainButtons:
    """Клавиатуры для админ-панели"""

    REGISTARATION_CODE = "Код регистрации"
    SHOPS = "Магазины"
    COURIERS = "Курьеры"
    ORDERS = "Заказы"
    DISPUTES = "Споры"
    STATISTICS = "Статистика"
    EDIT_PROFILE = "Редактировать профиль"


class AdminRegistrationCodesMenuButtons:
    """Клавиши меню 'Код регистрации' для админ-панели"""

    CREATE_CODE_FOR_COURIER = "Создать код для курьера"
    CREATE_CODE_FOR_SHOP = "Создать код для магазина"
    VIEW_REGISTRATION_CODES = "Список кодов регистрации"
    BACK = "Назад"


class AdminMessages:
    REGISTRATION_CODE_MENU = "Код регистрации позволяет зарегистрироваться новым пользователям."
    ADMIN_MAIN_MENU = """Главное меню бота:

Активные заказы: {active_orders}
Активные курьеры: {active_couriers}
Всего заказов сегодня: {orders_today}
Активные споры: {active_disputes}"""
