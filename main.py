import asyncio
import logging
import sys
from aiogram.utils.i18n import I18n
from bot.dispatcher import bot
from bot.handlers import dp
from bot.middlewares import all_middlewares
from database.create_tables import create_tables

i18n = I18n(path="locales", default_locale="en", domain="messages")


async def main():
    await all_middlewares(dp, i18n)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(create_tables())
    asyncio.run(main())
