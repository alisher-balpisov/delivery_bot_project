from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Состояния для создания заказа"""

    waiting_for_description = State()
    waiting_for_pickup_address = State()
    waiting_for_delivery_address = State()
    waiting_for_price = State()
    confirmation = State()


class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""

    waiting_for_code = State()
