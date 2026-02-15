"""FSM состояния для споров."""

from aiogram.fsm.state import State, StatesGroup


class DisputeStates(StatesGroup):
    """Состояния процесса спора."""

    waiting_for_reason = State()
