from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    waiting_for_comment = State()
    waiting_for_message = State()
    waiting_for_custom_slug = State()


class AdminStates(StatesGroup):
    waiting_for_add_admin = State()
    waiting_for_remove_admin = State()
    waiting_for_broadcast = State()
    waiting_for_ban = State()
    waiting_for_unban = State()
    waiting_for_lookup = State()


class LanguageStates(StatesGroup):
    language = State()
