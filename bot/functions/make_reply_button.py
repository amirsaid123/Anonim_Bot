from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.utils.i18n import gettext as _


async def make_reply_button(btns_name: list, adjust: list):
    rkb = ReplyKeyboardBuilder()
    rkb.add(*[KeyboardButton(text=name) for name in btns_name])
    rkb.adjust(*adjust)
    return rkb.as_markup(resize_keyboard=True, one_time_keyboard=True)


async def make_back_button():
    rkb = ReplyKeyboardBuilder()
    rkb.add(KeyboardButton(text=_("Back ◀️")))
    return rkb.as_markup(resize_keyboard=True, one_time_keyboard=True)


async def make_language_button():
    rkb = ReplyKeyboardBuilder()
    rkb.add(KeyboardButton(text="🇺🇸 English"),
            KeyboardButton(text="🇷🇺 Русский"),
            KeyboardButton(text="🇺🇿 O'zbekcha"),
            KeyboardButton(text=_("Back 🔙"))
            )
    rkb.adjust(3, 1)
    return rkb.as_markup(resize_keyboard=True, one_time_keyboard=True)
