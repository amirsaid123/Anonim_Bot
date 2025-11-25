from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def make_inline_button(btns_name: list, adjust: list):
    inline = InlineKeyboardBuilder()
    inline.add(
        *[
            InlineKeyboardButton(
                text=name,
                callback_data=f"{name.split()[0].lower()}"
            )
            for name in btns_name
        ]
    )
    inline.adjust(*adjust)
    return inline.as_markup()
