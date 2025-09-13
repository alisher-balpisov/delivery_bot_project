"""
Обработчики заказов для магазинов и курьеров
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import OrderStatus, UserRole
from backend.src.core.logging import get_logger

from bot.clients import client_manager
from bot.constants import ErrorMessages

logger = get_logger(__name__)

# Защищенный роутер для заказов
orders_router = Router(name="orders_router")
orders_router.message.filter(F.chat.type == "private")


class OrderStates(StatesGroup):
    """Состояния для создания заказа"""

    waiting_for_description = State()
    waiting_for_pickup_address = State()
    waiting_for_delivery_address = State()
    waiting_for_price = State()
    confirmation = State()


@orders_router.message(Command("new_order"))
async def new_order_handler(message: Message, state: FSMContext, user_data: dict):
    """Начать создание нового заказа (только для магазинов)."""
    role = user_data.get("role")

    if role != UserRole.SHOP:
        await message.answer(ErrorMessages.Orders.SHOPS_ONLY)
        return

    await state.set_state(OrderStates.waiting_for_description)
    await message.answer(
        "📦 Создание нового заказа\n\nШаг 1/4: Введите описание заказа (что нужно доставить):"
    )


@orders_router.message(OrderStates.waiting_for_description)
async def order_description_handler(message: Message, state: FSMContext):
    """Обработка описания заказа."""
    await state.update_data(description=message.text)
    await state.set_state(OrderStates.waiting_for_pickup_address)
    await message.answer("Шаг 2/4: Введите адрес забора товара:")


@orders_router.message(OrderStates.waiting_for_pickup_address)
async def order_pickup_handler(message: Message, state: FSMContext):
    """Обработка адреса забора."""
    await state.update_data(pickup_address=message.text)
    await state.set_state(OrderStates.waiting_for_delivery_address)
    await message.answer("Шаг 3/4: Введите адрес доставки:")


@orders_router.message(OrderStates.waiting_for_delivery_address)
async def order_delivery_handler(message: Message, state: FSMContext):
    """Обработка адреса доставки."""
    await state.update_data(delivery_address=message.text)
    await state.set_state(OrderStates.waiting_for_price)
    await message.answer("Шаг 4/4: Введите стоимость доставки (в тенге):")


@orders_router.message(OrderStates.waiting_for_price)
async def order_price_handler(message: Message, state: FSMContext):
    """Обработка цены и подтверждение."""
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer(ErrorMessages.Orders.INVALID_PRICE)
            return
    except ValueError:
        await message.answer(ErrorMessages.Orders.PRICE_FORMAT_ERROR)
        return

    await state.update_data(price=price)
    data = await state.get_data()

    # Показываем подтверждение
    confirm_text = (
        "📋 Подтвердите заказ:\n\n"
        f"📦 Описание: {data['description']}\n"
        f"📍 Забор: {data['pickup_address']}\n"
        f"🎯 Доставка: {data['delivery_address']}\n"
        f"💰 Цена: {price} ₸\n"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="order_confirm"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="order_cancel"),
            ]
        ]
    )

    await state.set_state(OrderStates.confirmation)
    await message.answer(confirm_text, reply_markup=keyboard)


@orders_router.callback_query(F.data == "order_confirm", OrderStates.confirmation)
async def order_confirm_handler(callback: CallbackQuery, state: FSMContext, user_data: dict):
    """Подтверждение и создание заказа."""
    data = await state.get_data()
    token = user_data.get("access_token")

    await callback.message.edit_text("🔄 Создаю заказ...")

    order_data = {
        "description": data["description"],
        "pickup_address": data["pickup_address"],
        "delivery_address": data["delivery_address"],
        "price": data["price"],
        "status": OrderStatus.CREATED,
    }

    result = await client_manager.orders.create_order(token, order_data)

    if result and result.get("id"):
        await callback.message.edit_text(
            f"✅ Заказ #{result['id']} успешно создан!\n\nОжидайте, когда курьер примет заказ."
        )
        await state.clear()
    else:
        error_msg = result.get("detail", "Неизвестная ошибка") if result else "Ошибка сервера"
        await callback.message.edit_text(ErrorMessages.Orders.order_creation_error(error=error_msg))

    await callback.answer()


@orders_router.callback_query(F.data == "order_cancel", OrderStates.confirmation)
async def order_cancel_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена создания заказа."""
    await state.clear()
    await callback.message.edit_text(ErrorMessages.Orders.ORDER_CANCELLED)
    await callback.answer()


@orders_router.message(Command("available_orders"))
async def available_orders_handler(message: Message, user_data: dict):
    """Показать доступные заказы для курьеров."""
    role = user_data.get("role")

    if role != UserRole.COURIER:
        await message.answer(ErrorMessages.Orders.COURIERS_ONLY)
        return

    token = user_data.get("access_token")
    orders = await client_manager.orders.get_available_orders(token)

    if not orders:
        await message.answer("📭 Нет доступных заказов.")
        return

    for order in orders[:5]:  # Показываем первые 5
        text = (
            f"📦 Заказ #{order.get('id')}\n"
            f"📍 Откуда: {order.get('pickup_address')}\n"
            f"🎯 Куда: {order.get('delivery_address')}\n"
            f"💰 Оплата: {order.get('price')} ₸\n"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Принять заказ", callback_data=f"take_order_{order.get('id')}"
                    )
                ]
            ]
        )

        await message.answer(text, reply_markup=keyboard)


@orders_router.callback_query(F.data.startswith("take_order_"))
async def take_order_handler(callback: CallbackQuery, user_data: dict):
    # ИСПРАВЛЕНО: Убрана лишняя переменная и код стал чище
    try:
        order_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("Неверный ID заказа")
        return

    token = user_data.get("access_token")

    result = await client_manager.orders.update_order_status(
        token,
        order_id,
        {"status": OrderStatus.ACCEPTED, "courier_id": user_data.get("user", {}).get("id")},
    )

    if result and result.get("success") is not False:
        await callback.message.edit_text(
            f"✅ Вы приняли заказ #{order_id}!\n"
            "Используйте /my_orders для просмотра активных заказов."
        )
    else:
        error_msg = result.get("detail", "Заказ уже принят") if result else "Ошибка"
        await callback.message.edit_text(ErrorMessages.Orders.order_accept_error(error=error_msg))

    await callback.answer()
