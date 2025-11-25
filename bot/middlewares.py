from aiogram import Dispatcher
from aiogram.utils.i18n import FSMI18nMiddleware

async def all_middlewares(dp: Dispatcher, i18n):
    dp.update.middleware(FSMI18nMiddleware(i18n))




