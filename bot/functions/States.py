from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    waiting_for_comment = State()
    waiting_for_message = State()
    waiting_for_add_admin = State()
    waiting_for_remove_admin = State()

class LanguageStates(StatesGroup):
    language = State()