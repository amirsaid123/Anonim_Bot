from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    waiting_for_comment = State()
    waiting_for_message = State()

class LanguageStates(StatesGroup):
    language = State()