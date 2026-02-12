"""
Модуль сообщений для заказов.
"""

from typing import Final


class OrderMessages:
    """Сообщения, связанные с заказами."""

    STEP_1_DESCRIPTION: Final = (
        "📦 **Создание нового заказа**\n\nШаг 1/4: Введите описание заказа (что нужно доставить):"
    )

    STEP_2_PICKUP: Final = "Шаг 2/4: Введите адрес забора товара:"

    STEP_3_DELIVERY: Final = "Шаг 3/4: Введите адрес доставки:"

    STEP_4_PRICE: Final = "Шаг 4/4: Введите стоимость доставки (в тенге):"

    CONFIRMATION_PROMPT: Final = (
        "📋 **Подтвердите заказ:**\n\n"
        "📦 Описание: {description}\n"
        "📍 Забор: {pickup_address}\n"
        "🎯 Доставка: {delivery_address}\n"
        "💰 Цена: {price} ₸\n"
    )

    CREATING_ORDER: Final = "🔄 Создаю заказ..."

    SUCCESSFULLY_CREATED: Final = (
        "✅ Заказ #{order_id} успешно создан!\n\nВ ближайшее время ожидайте курьера {courier_name}."
    )
    SUCCESSFULLY_CREATED_NO_COURIER: Final = (
        "✅ Заказ #{order_id} успешно создан!\n\nНа данный момент нет свободных курьеров"
    )

    NO_AVAILABLE_ORDERS: Final = "📭 Нет доступных заказов."

    ORDER_ACCEPTED: Final = (
        "✅ Вы приняли заказ #{order_id}\nИспользуйте /my_orders для просмотра активных заказов."
    )

    AVAILABLE_ORDER_TEMPLATE: Final = (
        "📦 **Заказ #{order_id}**\n"
        "📍 Откуда: {pickup_address}\n"
        "📝 Описание/Адрес: {description}\n"
        "💰 Оплата: {price} ₸\n"
    )

    ORDER_CANCELLED: Final = "❌ Создание заказа отменено."


class OrderErrors:
    """Сообщения об ошибках для заказов."""

    GENERAL_ERROR: Final = "❌ Произошла ошибка. Попробуйте позже."
    SHOPS_ONLY: Final = "❌ Только магазины могут создавать заказы."
    INVALID_PRICE: Final = "❌ Цена должна быть больше 0. Попробуйте еще раз:"
    PRICE_FORMAT_ERROR: Final = "❌ Введите корректную цену (число):"
    ORDER_CREATION_ERROR: Final = "❌ Ошибка создания заказа: {error}"
    COURIERS_ONLY: Final = "❌ Только курьеры могут просматривать доступные заказы."
    ORDER_ACCEPT_ERROR: Final = "❌ Не удалось принять заказ: {error}"
    NO_ORDERS_FOUND: Final = "❌ Доступные заказы не найдены для вашей роли."
