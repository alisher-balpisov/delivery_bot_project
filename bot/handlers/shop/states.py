from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Состояния для создания заказа"""

    # Шаг 1: Ввод описания заказа
    waiting_for_description = State()
    # Шаг 2: Установка цены заказа
    waiting_for_price = State()
    # Шаг 3: Установка времени доставки (для типа TIME)
    waiting_for_time = State()
    # Шаг 4: Подтверждение заказа
    confirmation = State()
    # Дополнительный шаг: Ожидание доп. информации
    waiting_for_order_info = State()
