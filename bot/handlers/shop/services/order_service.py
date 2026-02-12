"""Сервис создания заказов."""

import html
from datetime import datetime
from typing import Any

from backend.src.common.enums import DeliveryTimeType, OrderType
from backend.src.core.logging import get_logger

from bot.clients.orders_client import OrdersClient

logger = get_logger(__name__)


class OrderCreationService:
    """Сервис создания заказов через API."""

    @staticmethod
    async def create_order(
        token: str,
        order_details: dict[str, Any],
        orders_client: OrdersClient,
    ) -> tuple[bool, str]:
        """
        Создает заказ через API.

        Args:
            token: Токен авторизации
            order_details: Данные заказа из FSM
            orders_client: Клиент API заказов

        Returns:
            Tuple(успех, сообщение)
        """
        if not token:
            return False, "⚠️ Ошибка авторизации"

        # Подготовка данных
        price = order_details.get("price")
        order_data = {
            "description": order_details.get("description"),
            "price": int(price) if price is not None else None,
            "order_type": order_details.get("order_type", OrderType.REGULAR.value),
            "delivery_time_type": order_details.get(
                "delivery_time_type", DeliveryTimeType.TODAY.value
            ),
        }

        # Время доставки
        delivery_time = order_details.get("delivery_time")
        if delivery_time:
            if isinstance(delivery_time, datetime):
                order_data["delivery_time"] = delivery_time.isoformat()
            else:
                order_data["delivery_time"] = delivery_time

        # Курьер для не-REGULAR типов
        order_type = order_details.get("order_type")
        if order_type and order_type != OrderType.REGULAR.value:
            courier_id = order_details.get("courier_id")
            if courier_id:
                order_data["courier_id"] = courier_id

        try:
            logger.info(f"Создание заказа: {order_data}")
            result = await orders_client.create_order(token, order_data)

            if result.success and isinstance(result.data, dict) and result.data.get("id"):
                return OrderCreationService._format_success_message(result.data)
            else:
                error_msg = result.detail or "Неизвестная ошибка"
                escaped_error = html.escape(error_msg)
                return False, f"❌ Ошибка создания заказа: {escaped_error}"

        except Exception as e:
            logger.error(f"Критическая ошибка при создании заказа: {e}", exc_info=True)
            return False, "❌ Произошла ошибка при создании заказа. Попробуйте позже."

    @staticmethod
    def _format_success_message(order_data: dict) -> tuple[bool, str]:
        """Форматирует сообщение об успешном создании."""
        order_id = order_data["id"]
        courier_id = order_data.get("courier_id")
        courier_full_name = order_data.get("courier_full_name")

        if not courier_id or not courier_full_name:
            return True, (
                f"✅ <b>Заказ #{order_id} успешно создан!</b>\n\n"
                "Курьер будет назначен автоматически."
            )

        # Безопасно извлекаем имя
        name_parts = courier_full_name.split()
        display_name = name_parts[1] if len(name_parts) > 1 else courier_full_name
        escaped_name = html.escape(display_name)

        return True, (f"✅ <b>Заказ #{order_id} успешно создан!</b>\n\n🚚 Курьер: {escaped_name}")

    @staticmethod
    def get_order_type_requirements(order_type: str) -> dict[str, Any]:
        """Возвращает требования для типа заказа."""
        requirements = {
            OrderType.REGULAR.value: {
                "needs_courier": False,
                "needs_time": False,
                "description": "Обычный заказ. Курьер назначается автоматически.",
            },
            OrderType.TIME.value: {
                "needs_courier": True,
                "needs_time": True,
                "description": "Доставка к определённому времени.",
            },
            OrderType.DISTANCE.value: {
                "needs_courier": True,
                "needs_time": False,
                "description": "Дальняя доставка.",
            },
            OrderType.CUSTOM.value: {
                "needs_courier": True,
                "needs_time": False,
                "description": "Особый заказ (габаритный груз).",
            },
            OrderType.SUPPLY.value: {
                "needs_courier": True,
                "needs_time": False,
                "description": "Доставка со склада.",
            },
        }

        return requirements.get(order_type, requirements[OrderType.REGULAR.value])
