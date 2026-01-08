class ShopMainKeyboardsButtons:
    """Клавиши главного меню магазина"""

    CREATE_ORDER = "Создать заказ"
    CURRENT_ORDERS = "Текущие заказы"
    ORDER_HISTORY = "История заказов"
    STATISTICS = "Статистика"
    EDIT_PROFILE = "Редактировать профиль"


class ShopMessages:
    """Сообщения для магазина"""

    MAIN_MENU = (
        "Активные заказы : {active_orders}\n"
        "Всего заказов сегодня : {today_orders}\n"
        "Активные споры : {active_disputes}"
    )
