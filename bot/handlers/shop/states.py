"""FSM состояния для магазина."""

from aiogram.fsm.state import State, StatesGroup


class OrderCreateStates(StatesGroup):
    """Состояния процесса создания заказа."""

    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_time = State()
    waiting_for_courier = State()
    editing_description = State()
    editing_type = State()
    editing_price = State()
    confirmation = State()


class ProfileEditStates(StatesGroup):
    """Состояния редактирования профиля магазина."""

    waiting_for_name = State()
    waiting_for_address = State()
    waiting_for_phone = State()


class OrderActionStates(StatesGroup):
    """Состояния для действий с существующими заказами."""

    waiting_for_price = State()
    waiting_for_note = State()
    waiting_for_description = State()
    waiting_for_courier_change = State()
