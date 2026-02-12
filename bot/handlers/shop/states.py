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
    # Шаг 5: Выбор курьера (для нерегулярных заказов)
    waiting_for_courier = State()
    # Дополнительный шаг: Ожидание доп. информации
    waiting_for_order_info = State()
    # Шаг для редактирования описания на этапе подтверждения
    editing_description = State()
    # Шаг для редактирования типа заказа
    editing_type = State()
    # Шаг для редактирования цены
    editing_price = State()


class EditProfileStates(StatesGroup):
    """Состояния для редактирования профиля магазина"""

    # Ожидание нового названия магазина
    waiting_for_name = State()
    # Ожидание нового адреса
    waiting_for_address = State()
    # Ожидание нового телефона
    waiting_for_phone = State()


class OrderActionStates(StatesGroup):
    """Состояния для действий с существующим заказом"""

    # Ожидание ввода цены (если она не была указана при создании)
    waiting_for_price = State()
    # Ожидание ввода заметки к заказу
    waiting_for_note = State()
    # Ожидание ввода нового адреса
    waiting_for_address = State()
    # Ожидание ввода нового описания
    waiting_for_description = State()
    # Ожидание ввода нового курьера
    waiting_for_courier_change = State()
