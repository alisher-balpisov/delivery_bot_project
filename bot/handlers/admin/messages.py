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

    # ==================== Споры (Disputes) ====================
    DISPUTES_LIST_TITLE = "⚖️ <b>Споры</b>\nВсего: {total_count}"
    NO_DISPUTES_FOUND = "Споры не найдены."
    DISPUTE_NOT_FOUND = "Спор не найден."

    DISPUTE_DETAILS_TEMPLATE = (
        "⚖️ <b>Спор #{dispute_id}</b>\n\n"
        "📦 <b>Заказ:</b> #{order_id}\n"
        "📊 <b>Статус спора:</b> {status_emoji} {status}\n"
        "🏪 <b>Магазин:</b> {shop_name}\n"
        "👤 <b>Курьер:</b> {courier_name}\n"
        "🙋 <b>Открыл:</b> {opened_by_role}\n"
        "📅 <b>Создан:</b> {created_at}\n"
        "✅ <b>Решён:</b> {resolved_at}\n\n"
        "📝 <b>Описание проблемы:</b>\n{description}"
    )

    DISPUTE_STATUS_UPDATED = "✅ Статус спора успешно обновлён!"
    DISPUTE_STATUS_UPDATE_ERROR = "❌ Ошибка при обновлении статуса спора."
